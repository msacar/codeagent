import os
from dotenv import load_dotenv
import cocoindex
from cocoindex import utils as cx_utils
from sentence_transformers import SentenceTransformer
import torch

from .ops_parse import parse_file_to_symbols
from .ops_chunks import symbols_to_chunks
from .ops_summarize import summarize_chunk, extract_summary_field
from psycopg_pool import ConnectionPool
from .pagerank_update import update_pagerank
import numpy as np
from numpy.typing import NDArray
import os, re

def _slug(s: str | None) -> str:
    # fall back to a stable default if None/empty
    if not s:
        s = "default"
    s = re.sub(r'[^a-zA-Z0-9_]+', '_', s).strip('_').lower()
    # schemas cannot start with a digit; also handle empty after cleaning
    if not s or s[0].isdigit():
        s = f"r_{s}"
    return s

# Embedding set-up (one active model -> one column)
# -------------------------------------------------------------------------------------------------
# Env controls
_EMBED_PROVIDER = os.getenv("EMBED_PROVIDER", "bge").lower()  # "bge" | "voyage"
# Model ids:
#  - BGE: Hugging Face id (e.g., "BAAI/bge-code-v1")
#  - Voyage: API model name (e.g., "voyage-code-3")
_EMBED_MODEL = os.getenv("EMBED_MODEL") or ("BAAI/bge-code-v1" if _EMBED_PROVIDER == "bge" else "voyage-code-3")

# Voyage supports 512 / 1024 / 2048 output dims. We default to 1024 if not provided.
_EMBED_DIM = int(os.getenv("EMBED_DIM")) if os.getenv("EMBED_DIM") else (None if _EMBED_PROVIDER == "bge" else 1024)

@cocoindex.transform_flow()
def embed_with_bge(
    text: cocoindex.DataSlice[str],
) -> cocoindex.DataSlice[list[float]]:
    # Local sentence-transformers model from Hugging Face cache
    return text.transform(
        cocoindex.functions.SentenceTransformerEmbed(
            model=_EMBED_MODEL,  # e.g., "BAAI/bge-code-v1"
        )
    )

@cocoindex.transform_flow()
def embed_with_voyage(
    text: cocoindex.DataSlice[str],
) -> cocoindex.DataSlice[list[float]]:
    # Remote Voyage API (requires VOYAGE_API_KEY); output_dimension must be 512/1024/2048
    print(_EMBED_DIM)
    return text.transform(
        cocoindex.functions.EmbedText(
            api_type=cocoindex.LlmApiType.VOYAGE,
            model=_EMBED_MODEL,           # e.g., "voyage-code-3"
            task_type="document",
            output_dimension=_EMBED_DIM or 1024,
        )
    )


# do not need for now !
# @cocoindex.transform_flow()
# def chunk_text_to_embedding(
#     text: cocoindex.DataSlice[str],
# ) -> cocoindex.DataSlice[list[float]]:
#     return text.transform(
#         cocoindex.functions.SentenceTransformerEmbed(
#             model="sentence-transformers/all-MiniLM-L6-v2"
#         )
#     )


@cocoindex.flow_def(name="CodeIndex")
def build_index(flow_builder: cocoindex.FlowBuilder, data_scope: cocoindex.DataScope):
    root_dir = os.getenv("CODEAGENT_ROOT", os.getcwd())
    # derive repo name if not provided
    repo_name = os.getenv("CODEAGENT_REPO") or os.path.basename(root_dir)
    schema = os.getenv("CODEAGENT_SCHEMA") or _slug(repo_name)

    data_scope["files"] = flow_builder.add_source(
        cocoindex.sources.LocalFile(
            path=root_dir,
            included_patterns=["**/*.ts", "**/*.tsx", "**/*.js", "**/*.jsx", "**/*.py"],
            excluded_patterns=[
                "**/cdk.out/**",
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
            # 1) mevcut code embedding
            #ch["embedding"] = ch["text"].call(chunk_text_to_embedding)
            # 2) BGE-Code-v1 code embedding (1536-d)
            # Exactly ONE active embedding column named 'embedding'
            if _EMBED_PROVIDER == "bge":
                ch["embedding"] = ch["text"].call(embed_with_bge)
            elif _EMBED_PROVIDER == "voyage":
                ch["embedding"] = ch["text"].call(embed_with_voyage)
            else:
                raise ValueError(f"Unsupported EMBED_PROVIDER: {_EMBED_PROVIDER}")

            # # 2) summary JSON (Ollama)
            # ch["summary_json"] = ch["text"].transform(
            #     summarize_chunk,
            #     header=ch["header"],
            #     body=ch["body"],
            #     file=file["filename"],
            #     start=ch["start_line"],
            #     end=ch["end_line"],
            # )
            #
            # # 3) summary alanlarını çıkar
            # ch["summary_text"] = ch["summary_json"].transform(
            #     extract_summary_field, key="summary"
            # )
            # ch["summary_caps"] = ch["summary_json"].transform(
            #     extract_summary_field, key="capabilities"
            # )
            # ch["summary_idents"] = ch["summary_json"].transform(
            #     extract_summary_field, key="identifiers"
            # )
            # ch["summary_conf"] = ch["summary_json"].transform(
            #     extract_summary_field, key="confidence"
            # )
            # ch["content_sha"] = ch["summary_json"].transform(
            #     extract_summary_field, key="content_sha"
            # )
            #
            # # 4) summary embedding
            # ch["summary_embedding"] = ch["summary_text"].call(chunk_text_to_embedding)

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
                text=ch["text"],
                is_def=ch["is_def"],
                # NEW: summary fields
                # summary_text=ch["summary_text"],
                # summary_caps=ch["summary_caps"],
                # summary_idents=ch["summary_idents"],
                # summary_conf=ch["summary_conf"],
                # content_sha=ch["content_sha"],
                #embedding=ch["embedding"],
                embedding=ch["embedding"],
                # summary_embedding=ch["summary_embedding"],
            )

    embedding_def = cocoindex.VectorIndexDef(
        field_name="embedding",
        metric=cocoindex.VectorSimilarityMetric.COSINE_SIMILARITY,
        method=cocoindex.HnswVectorIndexMethod(ef_construction=128, m=16),
    )

    out.export(
        "code_chunks",
        cocoindex.targets.Postgres(
            table_name="code_chunks",  # stable across repos
            schema=schema  # <- isolates by schema
        ),
        primary_key_fields=["id"],
        vector_indexes=[embedding_def],
        attachments=[
            # ensure schema exists before we try to create indexes in it
            cocoindex.targets.PostgresSqlCommand(
                name="ensure_schema",
                setup_sql=(f"CREATE SCHEMA IF NOT EXISTS {schema};")
            ),
            # Example: extra helpers (GIN trigram) for lexical speed
            cocoindex.targets.PostgresSqlCommand(
                name="lexical",
                setup_sql=(
                    "CREATE EXTENSION IF NOT EXISTS pg_trgm;"
                    f"CREATE INDEX IF NOT EXISTS {schema}_cc_header_trgm "
                    f"ON {schema}.code_chunks USING GIN (header gin_trgm_ops);"
                    f"CREATE INDEX IF NOT EXISTS {schema}_cc_body_trgm "
                    f"ON {schema}.code_chunks USING GIN (body gin_trgm_ops);"
                    f"CREATE INDEX IF NOT EXISTS {schema}_cc_text_trgm "
                    f"ON {schema}.code_chunks USING GIN (text gin_trgm_ops);"

                ),
            ),
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
            root_dir = os.getenv("CODEAGENT_ROOT", os.getcwd())
            repo_name = os.getenv("CODEAGENT_REPO") or os.path.basename(root_dir)
            schema = os.getenv("CODEAGENT_SCHEMA") or _slug(repo_name)
            table = f"{schema}.code_chunks"
            touched = update_pagerank(pool, table)
            print(f"Updated PageRank on {touched} chunk rows.")

            # Garbage collect stale chunks
            with pool.connection() as conn, conn.cursor() as cur:
                cur.execute(
                    f"""
                    WITH latest AS (
                      SELECT file, MAX(sha) AS latest_sha
                      FROM {table}
                      GROUP BY file
                    )
                    DELETE FROM {table} c
                    USING latest l
                    WHERE c.file = l.file AND c.sha <> l.latest_sha;
                """
                )
                print(f"Garbage-collected stale chunk rows: {cur.rowcount or 0}")
        except Exception as e:
            print("[WARN] PageRank update skipped:", e)
