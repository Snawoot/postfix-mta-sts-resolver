import pytest
import postfix_mta_sts_resolver.netstring as netstring

@pytest.mark.parametrize("reference,sample", [
    pytest.param(b'0:,', b'', id="empty_str"),
    pytest.param(b'1:X,', b'X', id="single_byte"),
])
def test_encode(reference, sample):
    assert reference == netstring.encode(sample)

@pytest.mark.parametrize("reference,sample", [
    pytest.param([b'',], b'00:,', id="null_string"),
    pytest.param([b'X',], b'01:X,', id="single_byte"),
    pytest.param([b'',b'X'], b'00:,1:X,', id="null_string_with_continuation"),
    pytest.param([b'X',b'X'], b'01:X,1:X,', id="single_byte_with_continuation"),
])
def test_leading_zeroes(reference, sample):
    assert reference == list(netstring.decode(sample))

@pytest.mark.parametrize("reference,sample", [
    pytest.param([], b'', id="nodata"),
    pytest.param([b''], b'0:,', id="empty"),
    pytest.param([b'5:Hello,6:World!,'], b'17:5:Hello,6:World!,,', id="nested"),
])
def test_decode(reference, sample):
    assert reference == list(netstring.decode(sample))

@pytest.mark.parametrize("encoded", [b':,', b'aaa:aaa'])
def test_bad_length(encoded):
    with pytest.raises(netstring.BadLength):
        list(netstring.decode(encoded))

@pytest.mark.parametrize("encoded", [b'3', b'3:', b'3:a', b'3:aa', b'3:aaa'])
def test_decode_incomplete_string(encoded):
    with pytest.raises(netstring.IncompleteNetstring):
        list(netstring.decode(encoded))

def test_abandoned_string_reader_handles():
    stream_reader = netstring.StreamReader()
    stream_reader.feed(b'0:,')
    string_reader = stream_reader.next_string()
    with pytest.raises(netstring.InappropriateParserState):
        string_reader = stream_reader.next_string()

@pytest.mark.parametrize("encoded", [b'0:_', b'3:aaa_'])
def test_bad_terminator(encoded):
    with pytest.raises(netstring.BadTerminator):
        list(netstring.decode(encoded))

@pytest.mark.parametrize("reference,sequence", [
    pytest.param([b''], [b'0', b':', b','], id="empty"),
    pytest.param([b'X', b'abc', b'ok'], [b'1:', b'X,3:abc,2:', b'ok,'], id="multiple_and_partial"),
    pytest.param([b'X', b'123456789', b'ok'], [b'1:', b'X,9:123', b'456', b'789', b',2:', b'ok,'], id="multiple_and_partial2"),
])
def test_stream_reader(reference, sequence):
    incoming = sequence[::-1]
    results = []
    stream_reader = netstring.StreamReader()
    while incoming:
        string_reader = stream_reader.next_string()
        res = b''
        while True:
            try:
                buf = string_reader.read()
            except netstring.WantRead:
                if incoming:
                    stream_reader.feed(incoming.pop())
                else:
                    break
            else:
                if not buf:
                    break
                res += buf
        results.append(res)
    assert results == reference

def test_stream_portions():
    stream_reader = netstring.StreamReader()
    string_reader = stream_reader.next_string()
    with pytest.raises(netstring.WantRead):
        string_reader.read()
    stream_reader.feed(b'1:')
    with pytest.raises(netstring.WantRead):
        string_reader.read()
    stream_reader.feed(b'X,9:123')
    assert string_reader.read() == b'X'
    assert string_reader.read() == b''
    string_reader = stream_reader.next_string()
    assert string_reader.read() == b'123'
    stream_reader.feed(b'456')
    assert string_reader.read() == b'456'
    stream_reader.feed(b'789')
    assert string_reader.read() == b'789'
    with pytest.raises(netstring.WantRead):
        string_reader.read()
    stream_reader.feed(b',2:')
    assert string_reader.read() == b''
    string_reader = stream_reader.next_string()
    with pytest.raises(netstring.WantRead):
        string_reader.read()
    stream_reader.feed(b'ok,')
    assert string_reader.read() == b'ok'
    assert string_reader.read() == b''
    string_reader = stream_reader.next_string()
    with pytest.raises(netstring.WantRead):
        string_reader.read()

@pytest.mark.parametrize("limit,sample", [
    (5, b'6:123456,'),
    (1024, b'9999:aaa'),
    (1024, b'9999:'),
    (1024, b'9999'),
])
def test_limit(limit, sample):
    stream_reader = netstring.StreamReader(limit)
    stream_reader.feed(sample)
    string_reader = stream_reader.next_string()
    with pytest.raises(netstring.TooLong):
        string_reader.read()
