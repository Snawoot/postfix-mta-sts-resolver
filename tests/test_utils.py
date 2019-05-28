import tempfile
import collections.abc
import enum
import itertools

import pytest
import postfix_mta_sts_resolver.utils as utils

@pytest.mark.parametrize("cfg", [None, {}])
def test_populate_cfg_defaults(cfg):
    res = utils.populate_cfg_defaults(cfg)
    assert isinstance(res['host'], str)
    assert isinstance(res['port'], int)
    assert 0 < res['port'] < 65536
    assert isinstance(res['cache_grace'], (int, float))
    assert isinstance(res['cache'], collections.abc.Mapping)
    assert res['cache']['type'] in ('redis', 'sqlite', 'internal')
    assert isinstance(res['default_zone'], collections.abc.Mapping)
    assert isinstance(res['zones'], collections.abc.Mapping)
    for zone in list(res['zones'].values()) + [res['default_zone']]:
        assert isinstance(zone, collections.abc.Mapping)
        assert 'timeout' in zone
        assert 'strict_testing' in zone

def test_empty_config():
    assert utils.load_config('/dev/null') == utils.populate_cfg_defaults(None)

@pytest.mark.parametrize("rec,expected", [
    ("v=STSv1; id=20160831085700Z;", {"v": "STSv1", "id": "20160831085700Z"}),
    ("v=STSv1;id=20160831085700Z;", {"v": "STSv1", "id": "20160831085700Z"}),
    ("v=STSv1; id=20160831085700Z", {"v": "STSv1", "id": "20160831085700Z"}),
    ("v=STSv1;id=20160831085700Z", {"v": "STSv1", "id": "20160831085700Z"}),
    ("v=STSv1;        id=20160831085700Z   ", {"v": "STSv1", "id": "20160831085700Z"}),
    ("", {}),
    ("   ", {}),
    (" ;   ;  ", {}),
    ("v=STSv1; id=20160831085700Z;;;", {"v": "STSv1", "id": "20160831085700Z"}),
])
def test_parse_mta_sts_record(rec, expected):
    assert utils.parse_mta_sts_record(rec) == expected

@pytest.mark.parametrize("contenttype,expected", [
    ("text/plain", True),
    ("TEXT/PLAIN", True),
    ("TeXT/PlAiN", True),
    ("text/plain;charset=utf-8", True),
    ("text/plain;charset=UTF-8", True),
    ("text/plain; charset=UTF-8", True),
    ("text/plain ; charset=UTF-8", True),
    ("application/octet-stream", False),
    ("application/octet-stream+text/plain", False),
    ("application/json+text/plain", False),
    ("text/plain+", False),
])
def test_is_plaintext(contenttype, expected):
    assert utils.is_plaintext(contenttype) == expected

class TextType(enum.Enum):
    ascii_byte_string = 1
    nonascii_byte_string = 2
    unicode_string = 3
    invalid_string = 4

text_args = [
    (b"aaa", TextType.ascii_byte_string),
    (b"\xff", TextType.nonascii_byte_string),
    ("aaa", TextType.unicode_string),
    (None, TextType.invalid_string),
    (0, TextType.invalid_string),
]

text_params = []
for length in range(0, 5):
    text_params.extend(itertools.product(text_args, repeat=length))

@pytest.mark.parametrize("vector", text_params)
def test_filter_text(vector):
    if any(typ is TextType.invalid_string for (_, typ) in vector):
        with pytest.raises(TypeError):
            for _ in utils.filter_text(val for (val, _) in vector):
                pass
    else:
        res = list(utils.filter_text(val for (val, _) in vector))
        nonskipped = (pair for pair in vector if pair[1] is not TextType.nonascii_byte_string)
        for left, (right_val, right_type) in zip(res, nonskipped):
            if right_type is TextType.unicode_string:
                assert left == right_val
            else:
                assert left.encode('ascii') == right_val

def test_setup_logger():
    with tempfile.NamedTemporaryFile('r') as tmpfile:
        logger = utils.setup_logger("test", utils.LogLevel.info, tmpfile.name)
        logger.info("Hello World!")
        assert "Hello World!" in tmpfile.read()

def test_setup_logger_stderr(capsys):
    logger = utils.setup_logger("test", utils.LogLevel.info)
    logger.info("Hello World!")
    captured = capsys.readouterr()
    assert "Hello World!" in captured.err
