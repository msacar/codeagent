# index
export CODEAGENT_ROOT=/Users/mustafaacar/retter/shortlink                                                                                           4663ms  14:51:51
export CODEAGENT_REPO=shortlink 
codeagent index

# query 
 codeagent query --q "handleStaticLinkData(" --mode code -k 10 \                                                                                     4663ms  14:51:51
        --rerank --rerank-provider voyage --rerank-model rerank-2.5-lite \
        --repo shortlink


# pagerank 
codeagent pagerank --topn 30 --repo shortlink


python -m codeagent.cli index --root /Users/mustafaacar/retter/shortlink 

cocoindex server -ci main.py --address 0.0.0.0:3000 --reload 


uvx --from huggingface_hub hf download BAAI/bge-code-v1
uvx --from huggingface_hub hf download BAAI/bge-reranker-v2-m3

uvx --from huggingface_hub hf download sentence-transformers/all-MiniLM-L6-v2


uvx --from huggingface_hub hf cache ls | grep -E 'BAAI/bge-code-v1|bge-reranker-v2-m3'





# choose fast cache dir (optional)
export HF_HOME="$HOME/.hf-cache"

# prefetch models to cache
uvx --from huggingface_hub hf download BAAI/bge-code-v1
uvx --from huggingface_hub hf download BAAI/bge-reranker-v2-m3

# later, run offline if you like
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1



