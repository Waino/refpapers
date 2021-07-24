#!/bin/bash

set -eu

TESTING_DIR=$(mktemp --directory refpapers.XXXXXXXXXX --tmpdir=/tmp)
CONF_DIR="${TESTING_DIR}/conf"
INDEX_DIR="${TESTING_DIR}/index"
DATA_DIR="${TESTING_DIR}/data"

pushd "${TESTING_DIR}"
echo "Performing integration test in ${TESTING_DIR}"

### Set up
mkdir -p "${CONF_DIR}"
mkdir -p "${INDEX_DIR}"
mkdir -p "${DATA_DIR}/topicA"
mkdir -p "${DATA_DIR}/topicB"
# some files to index
touch "${DATA_DIR}/topicA/A_-_T_2021.pdf"
touch "${DATA_DIR}/topicA/Author_-_Title_book_2021.pdf"
touch "${DATA_DIR}/topicB/Author_-_MoreTitle_survey_2020.pdf"
# dummy version forces reindexing
echo "dummy-version" > ${CONF_DIR}/schema_version

echo ""
echo "### Create a minimal conf, perform full indexing"
echo "'Extraction failed' messages are ok: dummy files are empty"
echo "refpapers index --confdir ${CONF_DIR}"
refpapers index --confdir "${CONF_DIR}" <<CREATEMINIMAL
y
${DATA_DIR}
${INDEX_DIR}
CREATEMINIMAL

echo ""
echo "### Perform a search (expecting 2 results)"
echo "refpapers search --confdir ${CONF_DIR} author"
refpapers search --confdir "${CONF_DIR}" author

echo ""
echo "### Perform a search (expecting 0 results)"
echo "refpapers search --confdir ${CONF_DIR} nosuch"
refpapers search --confdir "${CONF_DIR}" nosuch

echo ""
echo "### Show details using bibtex key"
echo "refpapers one --confdir ${CONF_DIR} author2021title"
refpapers one --confdir "${CONF_DIR}" author2021title

echo ""
echo "### Add one, delete one, then perform (full) indexing"
echo "rm ${DATA_DIR}/topicB/Author_-_MoreTitle_survey_2020.pdf"
rm "${DATA_DIR}/topicB/Author_-_MoreTitle_survey_2020.pdf"
echo "touch ${DATA_DIR}/topicB/Second_-_Phase_2020.pdf"
touch "${DATA_DIR}/topicB/Second_-_Phase_2020.pdf"
echo "refpapers index --confdir ${CONF_DIR}"
refpapers index --confdir "${CONF_DIR}"

echo ""
echo "### author2020more should no longer be returned"
echo "refpapers search --confdir ${CONF_DIR} author2020more"
refpapers search --confdir "${CONF_DIR}" author2020more

echo ""
echo "### but second2020phase should be found"
echo "refpapers search --confdir ${CONF_DIR} second"
refpapers search --confdir "${CONF_DIR}" second


popd
#rm -r "${TESTING_DIR}"
echo ""
echo "Integration test ran to completion"
