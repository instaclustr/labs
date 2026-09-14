# Copyright 2026 NetApp Instaclustr contributors. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

FROM docker.io/opensearchproject/opensearch:3.5.0

USER root

#
# ---------------------------------------------------------------------------
# Preloaded OpenSearch data
# ---------------------------------------------------------------------------
#
# IMPORTANT:
#
# The source data must come from a cleanly stopped OpenSearch 3.5.0 node.
#
# Runtime lock files must NOT be carried into the new image.
#

RUN rm -rf /usr/share/opensearch/data \
    && mkdir -p /usr/share/opensearch/data

COPY --chown=1000:1000 \
    opensearch/data/ \
    /usr/share/opensearch/data/

#
# Remove runtime OpenSearch/Lucene lock files.
#
# These must not be carried from the source node into the new container.
#
RUN rm -f \
    /usr/share/opensearch/data/nodes/*/node.lock \
    /usr/share/opensearch/data/nodes/*/_state/write.lock \
    /usr/share/opensearch/data/nodes/*/indices/*/*/index/write.lock

#
# ---------------------------------------------------------------------------
# Snapshot repository
# ---------------------------------------------------------------------------
#

RUN mkdir -p /mnt/snapshots

COPY --chown=1000:1000 \
    opensearch/snapshots/ \
    /mnt/snapshots/

RUN printf '\npath.repo: ["/mnt/snapshots"]\n' \
    >> /usr/share/opensearch/config/opensearch.yml

#
# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------
#

RUN chown -R 1000:1000 \
    /usr/share/opensearch/data \
    /mnt/snapshots

USER 1000