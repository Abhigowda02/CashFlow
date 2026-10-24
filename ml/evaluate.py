"""Run: python -m ml.evaluate path/to/canonical.csv."""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
from .data import load_csv
from .delay_model import fit

OFFSETS = [10, 20, 30, 45, 60]


def evaluate(path, output=None):
    table = load_csv(path).sort_values('issue_date', kind='stable')
    if len(table) < 4:
        raise ValueError('Need at least four invoices for time evaluation')
    cutoff = table.issue_date.iloc[min(int(len(table)*.7), len(table)-1)]
    train = table[table.issue_date < cutoff].copy()
    test = table[table.issue_date >= cutoff].copy()
    if train.empty or test.empty:
        raise ValueError('Need distinct issue dates on both sides of the split')
    # Reconstruct what was actually known at the training cutoff.
    end = train.due_date + pd.to_timedelta(train.duration, unit='D')
    observed_end = end.where(end < cutoff, cutoff)
    train['event'] = ((train.event == 1) & (end < cutoff)).astype(int)
    train['duration'] = (observed_end - train.due_date).dt.total_seconds() / 86400
    if 'paid_date' in train:
        train.loc[train.event == 0, 'paid_date'] = None
    model = fit(train, use_saved=False)
    paid = train[train.event == 1]
    medians = paid.groupby('customer_id').duration.median()
    default = float(paid.duration.median())
    baseline = test.customer_id.map(medians).fillna(default).to_numpy()
    probs, predictions = [], []
    for _, row in test.iterrows():
        invoice, customer = row.to_dict(), {'id': row.customer_id, 'segment': row.segment}
        probs.append(model.cdf(invoice, customer, OFFSETS))
        scale, shape = model._distribution(invoice, customer)
        predictions.append(scale * np.log(2)**(1/shape) - model.shift)
    forecasts = {'naive': np.zeros(len(test)), 'customer_median': baseline,
                 'survival': np.asarray(predictions)}
    probability = np.asarray(probs)
    events = test.event.to_numpy() == 1
    duration = test.duration.to_numpy()
    records = []
    for name, prediction in forecasts.items():
        mae = float(np.mean(np.abs(prediction[events]-duration[events]))) if events.any() else np.nan
        records.append(dict(model=name, metric='mae_paid_days', offset_days=np.nan,
                            predicted=mae, actual=np.nan, n=int(events.sum())))
        for j, offset in enumerate(OFFSETS):
            # Exclude invoices censored before this horizon: their status is unknown.
            known = events | (duration >= offset)
            pred = probability[:, j] if name == 'survival' else (prediction <= offset).astype(float)
            records.append(dict(model=name, metric='share_paid', offset_days=offset,
                                predicted=float(pred[known].mean()) if known.any() else np.nan,
                                actual=float((events[known] & (duration[known] <= offset)).mean()) if known.any() else np.nan,
                                n=int(known.sum())))
    result = pd.DataFrame(records)
    result['source'] = str(path)
    result['train_cutoff'] = cutoff.date().isoformat()
    result['train_n'] = len(train)
    result['test_n'] = len(test)
    output = Path(output) if output else Path(__file__).parent / 'results'
    output.mkdir(parents=True, exist_ok=True)
    result.to_csv(output / 'metrics.csv', index=False)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots()
    for name in forecasts:
        subset = result[(result.model == name) & (result.metric == 'share_paid')]
        ax.plot(subset.offset_days, subset.predicted, marker='o', label=name)
    ax.plot(subset.offset_days, subset.actual, 'k--', label='observed (known outcomes)')
    ax.set(xlabel='Days after due date', ylabel='Share paid', ylim=(0, 1),
           title=f'Calibration: {Path(path).name}')
    ax.legend()
    fig.tight_layout()
    fig.savefig(output / 'calibration.png')
    plt.close(fig)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv_path')
    parser.add_argument('--output')
    args = parser.parse_args()
    print(evaluate(args.csv_path, args.output).to_string(index=False))
