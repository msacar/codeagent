from codeagent.codesitter.parser import parse_defs_and_refs_from_text

TS = """
class S3Storage {
  async getDynamicInstance(a: string, b: string, c: string): Promise<void> { return; }
}
"""


def test_method_container_from_captures():
    defs, refs = parse_defs_and_refs_from_text(
        filename="modules/shortlink-api/src/utils/s3-storage.ts",
        rel="modules/shortlink-api/src/utils/s3-storage.ts",
        content=TS,
    )
    # find method def
    m = next(
        d
        for d in defs
        if d.symbol_kind in ("method", "function") and d.name == "getDynamicInstance"
    )
    assert m.container == "S3Storage"
