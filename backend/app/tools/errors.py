class ToolGatewayError(Exception):
    """Base class for safe tool gateway failures."""


class UnknownToolError(ToolGatewayError):
    pass


class ToolPolicyDenied(ToolGatewayError):
    pass


class ToolInputError(ToolGatewayError):
    pass
