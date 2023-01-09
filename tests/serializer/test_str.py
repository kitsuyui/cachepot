import string

from cachepot.serializer.str import StringSerializer


def test_str_serializer() -> None:
    serializer = StringSerializer()

    patterns = [
        "yes",
        string.ascii_letters,
        string.ascii_lowercase,
        string.ascii_uppercase,
        string.digits,
        string.hexdigits,
        string.octdigits,
        string.printable,
        string.punctuation,
        string.whitespace,
        "❗",  # emoji
    ]

    for original in patterns:
        serialized = serializer.serialize(original)
        deserialized = serializer.deserialize(serialized)
        assert deserialized == original
