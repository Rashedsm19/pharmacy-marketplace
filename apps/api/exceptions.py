"""Application exceptions whose responses carry structured data.

`detail` is a string in every response this API sends. That is not a style
preference — clients type it as text and render it, so an object there once put
`[object Object]` where React expected a sentence and blanked the page,
including the sign-in screen. The validation handler in `main.py` was written to
enforce it, moving the structured part to a sibling key (`fields`).

One raise had escaped that rule: the listing eligibility check answered 422 with
`detail` as a dict. The frontend classifier reads a non-string `detail` as "this
did not come from our application" and reported a genuine business rejection as
an infrastructure fault — telling the seller to retry something that can never
succeed, while hiding the reasons that would have told them why.

So the structured part moves to a sibling key here too, and the exception type
carries it. Anything that needs to answer with structure should subclass this
rather than reach for a dict `detail` again.
"""
from __future__ import annotations

from fastapi import HTTPException, status


class StructuredHTTPException(HTTPException):
    """An HTTPException whose extra data is serialised beside `detail`, not inside it."""

    #: Key the structured payload is published under, alongside `detail`.
    payload_key: str = "details"

    def __init__(self, status_code: int, detail: str, payload: object) -> None:
        super().__init__(status_code=status_code, detail=detail)
        self.payload = payload


class EligibilityRejected(StructuredHTTPException):
    """A batch failed one or more marketplace eligibility rules.

    Not retryable: nothing about repeating the request changes the outcome. The
    reasons are what the seller has to act on, so they travel in their own key
    where a client can list them.
    """

    payload_key = "reasons"

    def __init__(self, reasons: list[str]) -> None:
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="تعذر نشر الدفعة: لم تجتز شروط الأهلية.",
            payload=reasons,
        )
