# Native Python and model-service setup

This is the alternative to the Python lab container in [Task 1](../tasks/introduction.md). Python, dependencies, and model weights live in your own environment. OpenSearch and Dashboards still use the provided Compose definition, but you start only those two containers.

Choose one path. Native macOS on Apple Silicon uses the application's MLX runtime. Native Linux uses GGUF. On Windows, this guide uses an Ubuntu 24.04 WSL2 environment for Python and Make; it does not claim to configure a Windows-native C++ build of `llama-cpp-python`.

The source archive and the container do not define an independent Windows-native installation procedure. The default Podman lab remains the consistent path for Windows attendees.

## 1. Prepare host tools and the repository

Use the same prepared workshop repository checkout as the container guide. All commands below assume that your current directory is its root and contains `scripts/introduction/`. The repository URL is supplied by the workshop maintainer, not inferred by this guide.

### macOS on Apple Silicon

Install an ARM64 build of Python 3.12 and native build tools. With Homebrew already installed, use its [Python 3.12 formula](https://formulae.brew.sh/formula/python@3.12):

```bash
xcode-select --install
brew install python@3.12 cmake pkg-config git
python3.12 --version
python3.12 -c 'import platform; print(platform.system(), platform.machine())'
make --version
```

If the Xcode command-line tools are already installed, the first command may report that no installation is needed. The platform check should print `Darwin arm64`, not `x86_64` under Rosetta. The supplied MLX requirements are conditional on that exact platform combination.

### Ubuntu 24.04, including Ubuntu 24.04 in WSL2

The following package commands are specific to Ubuntu 24.04. Other Linux distributions need equivalent Python 3.12 and compiler packages.

```bash
sudo apt-get update
sudo apt-get install -y python3.12 python3.12-venv python3.12-dev \
  build-essential cmake ninja-build pkg-config libopenblas-dev git curl
python3.12 --version
make --version
```

For Windows, create or select the WSL2 Ubuntu distribution following the [Microsoft WSL installation guide](https://learn.microsoft.com/en-us/windows/wsl/install). Keep the checkout and virtual environment in the Linux filesystem. The commands that follow run in that WSL shell, not in PowerShell.

For the WSL path, run Podman and its Compose provider in the same WSL distribution as Python, and execute the OpenSearch commands there. This keeps Python and the published OpenSearch port on the same Linux host rather than assuming that localhost crosses different Windows/WSL/Podman-machine environments. Use the [Podman installation instructions](https://podman.io/docs/installation) for that distribution and confirm `podman info` and `podman compose version` before continuing.

### Set the OpenSearch kernel prerequisite

OpenSearch requires the Linux kernel's `vm.max_map_count` to be at least `262144`. On Windows and macOS, configure the **Podman VM**, not the host operating system. [OpenSearch installation reference](https://docs.opensearch.org/latest/install-and-configure/install-opensearch/docker/)

**Windows or macOS - host terminal:**

```bash
podman machine ssh "sudo sysctl -w vm.max_map_count=262144"
podman machine ssh "sysctl vm.max_map_count"
```

**Linux with Podman running directly on the host:**

```bash
sudo sysctl -w vm.max_map_count=262144
sysctl vm.max_map_count
```

**Expected:** `vm.max_map_count = 262144`, or a larger existing value. A temporary `sysctl -w` setting may need to be reapplied after restarting the VM or host. For a persistent Linux setting, an administrator can place `vm.max_map_count=262144` in a file under `/etc/sysctl.d/` and run `sudo sysctl --system` in the same Linux environment.

## 2. Create the Python 3.12 environment

**Repository root:**

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python --version
python -m pip install --upgrade pip setuptools wheel
```

Expect Python `3.12.x`. Keep this environment separate from other projects so that the workshop's pinned dependencies do not replace packages in those environments.

On **macOS Apple Silicon**, install the unchanged dependency list:

```bash
CMAKE_ARGS='-DGGML_METAL=ON' \
  python -m pip install --no-binary=llama-cpp-python -r scripts/introduction/requirements.txt
python -m pip check
```

`llama-cpp-python` remains installed because it is in the supplied requirements, even though the native macOS workflow selects MLX. The runtime-specific imports in this task prevent an unused backend from being imported during another backend's startup.

On **Linux or WSL2**, install CPU PyTorch first, then the same dependency list:

```bash
python -m pip install 'torch>=2.7,<3' --index-url https://download.pytorch.org/whl/cpu
CMAKE_ARGS='-DGGML_BLAS=ON -DGGML_BLAS_VENDOR=OpenBLAS -DGGML_NATIVE=OFF' \
  CMAKE_BUILD_PARALLEL_LEVEL=2 \
  python -m pip install --no-binary=llama-cpp-python -r scripts/introduction/requirements.txt
python -m pip check
```

This selects a CPU build within the supplied PyTorch version range. The `llama-cpp-python` build uses OpenBLAS; consult its [installation documentation](https://llama-cpp-python.readthedocs.io/en/latest/) for platform-specific compiler errors. The macOS-only MLX entries are skipped on Linux by their requirement markers.

`pip check` should report no broken requirements. If a pinned release cannot be obtained from your configured package index, stop and resolve that release/index problem with the maintainer. Do not silently remove dependencies, change protocol versions, or relax pins to make installation appear successful.

## 3. Download the four model artifacts

**Repository root, virtual environment active:**

```bash
python scripts/introduction/native_download_models.py --selection all --models-dir "$HOME/models"
```

The script uses Hugging Face's [file and snapshot download APIs](https://huggingface.co/docs/huggingface_hub/guides/download). It downloads the two complete MLX model repositories, but only the specifically requested file from each GGUF repository—not every available quantization.

The resulting paths match the supplied model-service settings:

```text
~/models/
├── Qwen2.5-7B-Instruct-1M-4bit/
├── Qwen2.5-7B-Instruct-1M-Q5_K_M.gguf
├── Nemotron-Orchestrator-8B-q4_k_m.gguf
├── Orchestrator-8B-4bit/
└── model-manifest.json
```

This is a substantial download, approximately 20 GB before dependencies and other storage overhead. On failure, inspect network access and free disk space, then rerun the command. Downloading weights does not load them into RAM. The manifest records the resolved model revisions; it is not an inference-quality report.

The requested models are:

- [Qwen MLX](https://huggingface.co/mlx-community/Qwen2.5-7B-Instruct-1M-4bit)
- [Qwen GGUF](https://huggingface.co/bartowski/Qwen2.5-7B-Instruct-1M-GGUF/blob/main/Qwen2.5-7B-Instruct-1M-Q5_K_M.gguf)
- [Nemotron GGUF](https://huggingface.co/Mungert/Nemotron-Orchestrator-8B-GGUF/blob/main/Nemotron-Orchestrator-8B-q4_k_m.gguf)
- [Orchestrator MLX](https://huggingface.co/mlx-community/Orchestrator-8B-4bit)

Review their model cards and licenses before use or redistribution.

## 4. Start only OpenSearch and Dashboards

**On the same host that runs your native Python processes:**

```bash
podman compose -f scripts/introduction/docker-compose.yaml up -d opensearch dashboards
podman compose -f scripts/introduction/docker-compose.yaml ps
```

Do not start the `lab` service for this path. It would publish the same model ports that your native Python services need.

On macOS, Podman must have a running machine. On Linux or WSL2, the commands here assume a locally running Podman engine. Check the `vm.max_map_count` troubleshooting in [Task 1](../troubleshooting/introduction.md#troubleshoot-the-failed-check-not-a-different-layer) if OpenSearch does not become healthy.

Native processes reach the published OpenSearch port through loopback. With your Python virtual environment active:

```bash
export OPENSEARCH_HOST=127.0.0.1
export OPENSEARCH_PORT=9200
export OPENSEARCH_SSL=false
python scripts/introduction/native_verify_environment.py
```

Wait for all checks to pass before continuing. Open `http://127.0.0.1:5601` in your host browser for Dashboards. In WSL, use the published port from Windows only if localhost forwarding is enabled; the Python checks in the WSL distribution remain the reference for connectivity.

> **Local development only:** The supplied OpenSearch configuration disables security and disk-watermark allocation checks. The model APIs have no authentication and use Flask's development server. Published ports are restricted to `127.0.0.1`; do not expose this stack to a public or shared network. Monitor disk space rather than relying on the disabled OpenSearch disk thresholds. See the [OpenSearch development-container guidance](https://docs.opensearch.org/3.5/install-and-configure/install-opensearch/docker/).

## 5. Start the services in separate native terminals

Unlike an `exec` session, a new host terminal does not automatically select your repository or virtual environment. In **each** terminal, change into the `scripts/introduction` folder.

Then start Qwen in **Terminal 1**:

```bash
cd scripts/introduction/slm_service && make slm-service
```

Start Nemotron in **Terminal 2**:

```bash
cd scripts/introduction/orch_service && make orch-service
```

## 6. Verify and continue

In a third native terminal, return to the repository root, activate `.venv`, and set `OPENSEARCH_HOST=127.0.0.1` before running:

```bash
python scripts/introduction/native_verify_environment.py --services
```

On Apple Silicon, model health should report `runtime: mlx`. On Linux/WSL2 it should report `runtime: gguf`. Then run the two completion examples in [Task 1, Step 6](../tasks/introduction.md) directly in this native shell. Skip the `podman exec` instruction; your model processes are running on the host.

Keep the same environment active for subsequent tasks. You will use `OPENSEARCH_HOST=127.0.0.1`, not the container-only hostname `opensearch-single`, in those native agent processes.

### Native-only ingestion for Tasks 2 and 3

The default development-container walkthrough uses pre-populated corpora on OpenSearch hosted by Instaclustr and skips ingestion. **This native setup still requires `make ingest` for both agents** to prepare the corpora in your own OpenSearch instance. Run these commands only after native setup and OpenSearch connectivity have been verified. Do not run them against the shared hosted workshop indices.

The source archive does not contain the datasets. Obtain the workshop inputs before continuing: the news CSV must be at `scripts/news-agent/ai_media_dataset_20250911-1000lines.csv`, and the text-converted filing `.md` files, with any metadata sidecars, must be under `scripts/financials-agent/quarterly_filings/`. These are the defaults used by the existing ingestion commands, not files supplied in this ZIP. Keep the same embedding model for ingestion and subsequent query retrieval.

**Repository root, native Python environment active, and your own OpenSearch connection verified:**

```bash
(cd scripts/news-agent && make ingest)
```

**Expected:** the News Expert reports a positive article/chunk count and the target index after parsing the CSV, chunking articles, creating document embeddings, and indexing the source metadata. Counts depend on the supplied CSV. A missing input or connection error must be resolved before retrieval.

[News Make target](../scripts/news-agent/Makefile) · [News ingestion implementation](../scripts/news-agent/src/ingest.py)

From the same **repository root and native environment**, prepare the filing corpus:

```bash
(cd scripts/financials-agent && make ingest)
```

**Expected:** the Financial Expert logs a positive ingested-chunk count and the target index after discovering filings, retaining issuer/filing metadata, chunking, embedding, and indexing them. A missing input or a run with no filing chunks is not a completed corpus setup.

[Financial Make target](../scripts/financials-agent/Makefile) · [Filing ingestion implementation](../scripts/financials-agent/src/ingest.py)

Ingest each corpus before its corresponding task, then run [Task 2's corpus inspection](../tasks/news-agent.md#step-2-inspect-the-preloaded-historical-corpus) or [Task 3's corpus inspection](../tasks/financials-agent.md#step-2-inspect-the-preloaded-sec-corpus) from that agent's native source directory. Skip the container-entry commands and keep your native configuration active. Those read-only checks verify the indexed evidence before a generated answer depends on it. Rerun ingestion only when intentionally updating your own corpus, not as a routine retrieval or connection check.

## ONLY Upon completion of the lab

To stop all services, press Ctrl+C in all terminals and stop the supporting containers:

```bash
podman compose -f scripts/introduction/docker-compose.yaml stop opensearch dashboards
```

The virtual environment and `~/models` remain on your host. OpenSearch data remains in its named volume unless that volume is explicitly removed.
