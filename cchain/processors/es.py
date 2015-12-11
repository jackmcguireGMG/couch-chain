import logging

from cchain.processors import base
from cchain.processors import exceptions


logger = logging.getLogger(__name__)


class SimpleESChangesProcessor(base.BaseESChangesProcessor):
    """Stores documents in elasticsearch.

    """

    def __init__(self, es_urls, es_index, es_type, **kwargs):
        """

        :param es_urls: Urls of ES nodes.
        :param es_index: the name of the index to store documents in.
        :param es_type: what the `_type` property will be set to in es docs.
        :param seq_property: the name of the property that will be added
            to the document to store the relevant change sequence. If `None`,
            it won't be added at all.

        """

        super(
            SimpleESChangesProcessor,
            self
        ).__init__(es_urls, es_index, **kwargs)

        self._retry_on_conflict = kwargs.pop('retry_on_conflict', 3)
        self._es_type = es_type

    def get_index(self, doc):
        """Override this to send documents do various indices, depending
        on the content.

        :param doc: the document to be indexed.

        :returns: tne name of the index that the document will be sent to.

        """

        return self._es_index

    def get_type(self, doc):
        """Override this to change the type that the document will receive
        in elasticsearch.

        :param doc: the document to index.

        :returns: the type to assign to the document in ES.

        """

        return self._es_type

    def process_changes(self, changes_buffer):
        """Sticks the processed documents into elasticsearch.

        """

        processed_changes, last_seq = super(
            SimpleESChangesProcessor,
            self
        ).process_changes(changes_buffer)

        if not processed_changes:
            return processed_changes, last_seq

        return processed_changes, last_seq

    def persist_changes(self, processed_changes):
        """Stores the processed changes in es.

        :param processed_changes: a list of (doc, rev, seq) tuples.

        """
        bulk_ops = []

        for (doc, rev, seq, ) in processed_changes:
            doc_ops = self.get_ops_for_bulk(doc)
            bulk_ops += doc_ops

        error = False

        try:
            return_value = self._es.bulk(
                bulk_ops,
                timeout=self._bulk_timeout,
                request_timeout=self._request_timeout
            )
        except:
            logger.exception('Failed to index documents!')
            error = True
        else:
            if return_value.get('errors'):
                logger.debug('ES response: %s', return_value)
                logger.error('Errors executing bulk!')
                error = True

        if error:
            raise exceptions.ProcessingError

    def get_ops_for_bulk(self, doc):
        """Returns a list of operations to be performed in elasticsearch
        for the given document. By default, the document is "upserted".
        Override this if you need to merge your documents in a fancier way.

        :param doc: Document to be processed.

        :returns: a list of elasticsearch operations that can be passed
            into the bulk api.

        """

        ops = []

        op_data = {
            '_id': doc['_id'],
            '_type': self.get_type(doc),
            '_index': self.get_index(doc),
        }

        if doc.get('_deleted'):
            op_dict = {
                'delete': op_data,
            }
            ops.append(op_dict)
        else:
            op_data.update({
                '_retry_on_conflict': self._retry_on_conflict
            })
            op_dict = {
                'update': op_data,
            }
            ops.append(op_dict)
            data_dict = {
                'doc': doc,
                'doc_as_upsert': True
            }
            ops.append(data_dict)

        return ops
