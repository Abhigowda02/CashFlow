# Feature status

| Feature | Status | Test in under a minute | Tested |
| --- | --- | --- | --- |
| Review-first CSV/GST invoice import API | PARTIAL | Sign in, POST a CSV to `/api/invoices/preview`, then submit its edited rows to `/api/invoices/commit` with INR confirmation. | Mapper, GST error handling and preview/commit tests pass. UI upload/review flow remains to be added. |
