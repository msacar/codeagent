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

# Pick device & dtype once
_has_cuda = torch.cuda.is_available()
_has_mps = getattr(torch.backends, "mps", None) and torch.backends.mps.is_available()
_device = "cuda" if _has_cuda else ("mps" if _has_mps else "cpu")
_bge_kwargs = {"dtype": torch.float16} if _device in ("cuda", "mps") else {}


@cocoindex.transform_flow()
def chunk_text_to_embedding_bge(
    text: cocoindex.DataSlice[str],
) -> cocoindex.DataSlice[cocoindex.Vector[np.float32, 1536]]:
    return text.transform(
        cocoindex.functions.SentenceTransformerEmbed(
            model="BAAI/bge-code-v1",  # trust_remote_code is handled by SentenceTransformers
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
            ch["embedding"] = ch["text"].call(chunk_text_to_embedding_bge)

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
                embedding_bge=ch["embedding_bge"],
                # summary_embedding=ch["summary_embedding"],
            )

    embedding_def = cocoindex.VectorIndexDef(
        field_name="embedding",
        metric=cocoindex.VectorSimilarityMetric.COSINE_SIMILARITY,
        method=cocoindex.HnswVectorIndexMethod(ef_construction=128, m=16),
    )

    out.export(
        "code_chunks",
        cocoindex.targets.Postgres(),
        primary_key_fields=["id"],
        vector_indexes=[
            # cocoindex.VectorIndexDef(
            #     field_name="embedding",
            #     metric=cocoindex.VectorSimilarityMetric.COSINE_SIMILARITY,
            # ),
            # cocoindex.VectorIndexDef(
            #     field_name="summary_embedding",
            #     metric=cocoindex.VectorSimilarityMetric.COSINE_SIMILARITY,
            # ),
            embedding_def
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
