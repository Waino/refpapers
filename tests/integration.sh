#!/bin/bash

set -eu

TESTING_DIR=$(mktemp --directory papers2.XXXXXXXXXX)
INDEX_DIR="${TESTING_DIR}/index"
DATA_DIR="${TESTING_DIR}/data"

pushd "${TESTING_DIR}"
echo "Performing integration test in ${TESTING_DIR}"

#FIXME

popd
rm -r "${TESTING_DIR}"
echo "Integration test ran to completion"
