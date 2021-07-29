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
touch "${DATA_DIR}/topicA/Not_-_Shown_1900.pdf"
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


echo ""
echo "### switching to git tracking"

tee ${CONF_DIR}/conf.yml <<FULLCONF
fulltext_chars: 300000
extract_max_seconds: 1.0
use_git: True
git_uncommitted: "WARN"
paths:
    index: "${INDEX_DIR}"
    data: "${DATA_DIR}"
    log: "${CONF_DIR}/log"
software:
    viewers:
        pdf: "evince"
        djvu: "evince"
    extractors:
        pdf: "pdftotext -l 20"
        djvu: "None"
FULLCONF
pushd ${DATA_DIR}
git init
git add *
git commit -a -m "initial"
popd

echo ""
echo "### perform full reindexing"
echo "refpapers index --full --confdir ${CONF_DIR}"
refpapers index --full --confdir "${CONF_DIR}"

echo ""
echo "### Add one, delete one, modify one, then perform incremental indexing"
echo "# expecting one untracked warning"
echo "rm ${DATA_DIR}/topicB/Second_-_Phase_2020.pdf"
rm "${DATA_DIR}/topicB/Second_-_Phase_2020.pdf"
echo "git -C ${DATA_DIR} commit -a -m remove old"
git -C ${DATA_DIR} commit -a -m "remove old"
echo "touch ${DATA_DIR}/topicB/Third_-_Phase_2020.pdf"
touch "${DATA_DIR}/topicB/Third_-_Phase_2020.pdf"
echo "echo modified > ${DATA_DIR}/topicA/Author_-_Title_book_2021.pdf"
echo "modified" > "${DATA_DIR}/topicA/Author_-_Title_book_2021.pdf"
echo "git -C ${DATA_DIR} add ${DATA_DIR}/topicB/Third_-_Phase_2020.pdf"
git -C ${DATA_DIR} add "${DATA_DIR}/topicB/Third_-_Phase_2020.pdf"
echo "git -C ${DATA_DIR} commit -a -m phase 3"
git -C ${DATA_DIR} commit -a -m "phase 3"
echo "touch ${DATA_DIR}/topicA/Warn_-_Uncommitted.pdf"
touch "${DATA_DIR}/topicA/Warn_-_Uncommitted.pdf"
echo "refpapers index --confdir ${CONF_DIR}"
refpapers index --confdir "${CONF_DIR}"

echo ""
echo "### second2020phase should no longer be returned"
echo "refpapers search --confdir ${CONF_DIR} second2020phase"
refpapers search --confdir "${CONF_DIR}" second2020phase

echo ""
echo "### but third2020phase should be found"
echo "refpapers search --confdir ${CONF_DIR} third"
refpapers search --confdir "${CONF_DIR}" third

echo ""
echo "### original files should be found (expecting 1 result)"
echo "refpapers search --confdir ${CONF_DIR} author"
refpapers search --confdir "${CONF_DIR}" author


popd
#rm -r "${TESTING_DIR}"
echo ""
echo "Integration test ran to completion"
