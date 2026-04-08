"""Константы статусов откликов — единый источник истины."""

STATUS_SENT = "sent"
STATUS_COVER_LETTER = "cover_letter_sent"
STATUS_TEST_REQUIRED = "test_required"
STATUS_EXTRA_STEPS = "extra_steps"
STATUS_LETTER_REQUIRED = "letter_required"
STATUS_ALREADY_APPLIED = "already_applied"
STATUS_NO_BUTTON = "no_button"
STATUS_CAPTCHA = "captcha"
STATUS_ERROR = "error"
STATUS_FILTERED = "filtered"
STATUS_RATE_LIMITED = "rate_limited"

SUCCESS_STATUSES = (STATUS_SENT, STATUS_COVER_LETTER, "letter_sent")
