# Public Dataset Validation

## Dataset Size

- Private analysis rows: 1231
- Public rows: 1231
- Private students: 56
- Public students: 56
- Private questions: 68
- Public questions: 68
- Private sessions: 15
- Public sessions: 15

## Privacy Checks

- Only allowed public columns: True
- Direct identifiers absent: True
- Exact timestamps absent: True
- UUID-like values absent: True
- Email-like values absent: True
- IP-like values absent: True

## Primary Model Reproduction

Model: `correct ~ z_log_response_time * question_type + course + (1 | student_id) + (1 | question_id)`

- Maximum absolute fixed-effect coefficient difference: 0
- AIC difference: 0
- Log-likelihood difference: 0
- Private AIC: 1076.763369238196
- Public AIC: 1076.763369238196
- Private logLik: -529.3816846190978
- Public logLik: -529.3816846190978

Public dataset reproduces the reported primary analysis: PASS
