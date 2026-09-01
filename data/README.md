# Data

This directory contains the public reproducible dataset:

```text
leibtimeter_public.csv
```

## Data Dictionary

| Variable | Description |
|---|---|
| student_id | Synthetic persistent student identifier |
| course | Course context |
| session_id | Synthetic session identifier |
| question_id | Synthetic persistent question identifier |
| question_type | SingleChoice, MultipleChoice, or TrueFalse |
| response_time_seconds | Time from question opening to response submission |
| is_correct | Binary response correctness |

`student_id`, `session_id`, and `question_id` are synthetic and have no external meaning. The dataset does not include names, student codes, emails, IP addresses, device information, original internal UUIDs, original hashed student identifiers, or exact interaction timestamps.
