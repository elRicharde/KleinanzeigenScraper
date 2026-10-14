class UnexpectedHTMLResponse(RuntimeError): ...


class IPBlocked(UnexpectedHTMLResponse):
    """kleinanzeigen.de temporarily blocked the IP address"""
