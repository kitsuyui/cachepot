class CachepotWarning(UserWarning):
    """Base warning class for all cachepot-specific warnings.

    Use this class as the ``category`` argument when filtering or capturing
    warnings from cachepot:

        import warnings
        warnings.filterwarnings("error", category=CachepotWarning)

    or in tests:

        with pytest.warns(CachepotWarning):
            ...
    """
