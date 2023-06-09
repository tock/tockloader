class TockLoaderException(Exception):
    """
    Raised when Tockloader detects an issue.
    """

    pass


class ChannelAddressErrorException(Exception):
    """
    Raised when a particular channel to a board cannot support the request
    operation, likely due to the specific address.
    """

    pass
