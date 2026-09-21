"""
SQL Safety Layer errors for ScribeQL.
All safety violations raise SafetyError with a user-facing message.
Raw database or parser messages never appear here.
"""


class SafetyError(Exception):
    """Raised when generated SQL fails the AST safety check."""

    def __init__(self, error_type: str, message: str, stage: str = "safety"):
        self.stage = stage
        self.type = error_type
        self.message = message
        super().__init__(message)

    def to_dict(self) -> dict:
        return {
            "stage": self.stage,
            "type": self.type,
            "message": self.message,
        }
