from app.core.dn import decode_dn, encode_dn


def test_dn_roundtrip():
    dn = "CN=John Doe,OU=Sales+Loc,DC=corp,DC=local"
    enc = encode_dn(dn)
    # URL-safe：不应出现 + / = 等会破坏路径的字符
    assert "+" not in enc and "/" not in enc and "=" not in enc
    assert decode_dn(enc) == dn


def test_dn_special_chars():
    dn = "CN=Equals=Sign,OU=Test,DC=example,DC=com"
    assert decode_dn(encode_dn(dn)) == dn
