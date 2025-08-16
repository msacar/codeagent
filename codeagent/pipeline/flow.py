import os
from dotenv import load_dotenv
import cocoindex
from cocoindex import utils as cx_utils

from .ops_parse import parse_file_to_symbols
from .ops_chunks import symbols_to_chunks
from psycopg_pool import ConnectionPool
from .pagerank_update import update_pagerank


@cocoindex.transform_flow()
def chunk_text_to_embedding(
    text: cocoindex.DataSlice[str],
) -> cocoindex.DataSlice[list[float]]:
    return text.transform(
        cocoindex.functions.SentenceTransformerEmbed(
            model="sentence-transformers/all-MiniLM-L6-v2"
        )
    )


@cocoindex.flow_def(name="CodeIndex")
def build_index(flow_builder: cocoindex.FlowBuilder, data_scope: cocoindex.DataScope):
    root_dir = os.getenv("CODEAGENT_ROOT", os.getcwd())
    data_scope["files"] = flow_builder.add_source(
        cocoindex.sources.LocalFile(
            path=root_dir,
            included_patterns=["**/*.ts", "**/*.tsx", "**/*.js", "**/*.jsx", "**/*.py"],
            excluded_patterns=[
                "**/node_modules/**",
                "**/dist/**",
                "**/build/**",
                "**/.git/**",
                "**/.idea/**",
                "**/__pycache__/**",
                "**/__tests__/**",
            ],
        )
    )
    out = data_scope.add_collector()

    # For-each-row on the files table (one .row() only)
    with data_scope["files"].row() as file:
        # Per-row transforms live as fields on the row Struct to keep KTable V=Struct
        file["symbols"] = file["content"].transform(
            parse_file_to_symbols, filename=file["filename"]
        )
        file["chunks"] = file["symbols"].transform(
            symbols_to_chunks, filename=file["filename"], content=file["content"]
        )
        with file["chunks"].row() as ch:
            ch["embedding"] = ch["text"].call(chunk_text_to_embedding)
            out.collect(
                id=ch["id"],
                file=file["filename"],
                lang=ch["lang"],
                symbol_kind=ch["symbol_kind"],
                name=ch["name"],
                container=ch["container"],
                start=ch["start_line"],
                end=ch["end_line"],
                header=ch["header"],
                body=ch["body"],
                deps=ch["deps"],
                rank=ch["rank"],
                sha=ch["sha"],
                embedding=ch["embedding"],
            )

    out.export(
        "code_chunks",
        cocoindex.targets.Postgres(),
        primary_key_fields=["id"],
        vector_indexes=[
            cocoindex.VectorIndexDef(
                field_name="embedding",
                metric=cocoindex.VectorSimilarityMetric.COSINE_SIMILARITY,
            )
        ],
    )


def run_index():
    load_dotenv()
    cocoindex.init()
    # Create/align internal storage + target tables for this flow
    build_index.setup(report_to_stdout=True)
    stats = build_index.update()
    print("Updated index:", stats)
    # After chunks are written, compute & store PageRank like Aider
    db_url = os.environ.get("COCOINDEX_DATABASE_URL")
    if db_url:
        try:
            pool = ConnectionPool(db_url)
            # Resolve the table name for this build_index target
            table = cx_utils.get_target_default_name(build_index, "code_chunks")
            touched = update_pagerank(pool, table)
            print(f"Updated PageRank on {touched} chunk rows.")
        except Exception as e:
            print("[WARN] PageRank update skipped:", e)
