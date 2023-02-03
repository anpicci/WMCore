"""
File       : MSPileupData.py
Author     : Valentin Kuznetsov <vkuznet AT gmail dot com>
Description: MSPileupData provides logic behind
data used and stored by MSPileup module.

The data flow should be done via list of objects, e.g.
[<pileup object 1>, <pileup object 2>, ..., <pileup object n>]
"""

# third party modules
from pymongo import IndexModel, errors

# WMCore modules
from WMCore.Database.MongoDB import MongoDB
from WMCore.MicroService.MSPileup.DataStructs.MSPileupObj import MSPileupObj
from WMCore.MicroService.MSPileup.MSPileupError import MSPileupUniqueConstrainError, \
    MSPileupDatabaseError, MSPileupNoKeyFoundError, MSPileupDuplicateDocumentError
from WMCore.MicroService.Tools.Common import getMSLogger
from Utils.Timers import gmtimeSeconds


def stripKeys(docs, skeys=None):
    """
    Helper function to strip out keys from given dictionary.

    :param docs: either input dictionary or list of dictionaries
    :param skeys: list of of strip keys
    """
    if skeys is None:
        return docs
    if isinstance(docs, list):
        results = []
        for doc in docs:
            if doc:
                for key in skeys:
                    doc.pop(key, None)
                    results.append(doc)
        return results

    if docs and isinstance(docs, dict):
        for key in skeys:
            docs.pop(key, None)
    return docs


class MSPileupData():
    """
    MSPileupData provides logic behind data used and stored by MSPileup module
    """

    def __init__(self, msConfig, **kwargs):
        """
        Constructor for MSPileupData
        """
        self.logger = getMSLogger(False)
        self.msConfig = msConfig
        self.msConfig.setdefault("mongoDBRetryCount", 3)
        self.msConfig.setdefault("mongoDBReplicaSet", None)
        self.msConfig.setdefault("mongoDBPort", None)
        self.msConfig.setdefault("mockMongoDB", False)
        self.validRSEs = self.msConfig.get('validRSEs', [])

        # A full set of valid database connection parameters can be found at:
        # https://pymongo.readthedocs.io/en/stable/api/pymongo/mongo_client.html
        mongoIndex = IndexModel('pileupName', unique=True)
        collection = self.msConfig.get('mongoDBCollection', 'msPileupCollection')
        msOutDBConfig = {
            'database': self.msConfig['mongoDB'],
            'server': self.msConfig['mongoDBServer'],
            'replicaSet': self.msConfig['mongoDBReplicaSet'],
            'port': self.msConfig['mongoDBPort'],
            'username': self.msConfig['mongoDBUser'],
            'password': self.msConfig['mongoDBPassword'],
            'mockMongoDB': self.msConfig['mockMongoDB'],
            'connect': True,
            'directConnection': False,
            'logger': self.logger,
            'create': True,
            'collections': [(collection, mongoIndex)]}
        mongoDB = MongoDB(**msOutDBConfig)
        self.msDB = getattr(mongoDB, self.msConfig['mongoDB'])
        self.dbColl = self.msDB[collection]

    def createPileup(self, pdict):
        """
        Create and return pileup data from campaigns dictionary

        :param pdict: a dictionary representing MSPileup data
        :return: list of MSPileupError or empty list
        """
        # first, create MSPileupObj which will be validated against its schema
        try:
            obj = MSPileupObj(pdict, validRSEs=self.validRSEs)
            doc = obj.getPileupData()
        except Exception as exp:
            msg = f"Failed to create MSPileupObj, {exp}"
            self.logger.exception(msg)
            err = MSPileupDuplicateDocumentError(pdict, msg)
            self.logger.error(err)
            return [err.error()]

        # insert document into underlying DB
        try:
            self.dbColl.insert_one(doc)
            self.logger.info("Pileup object %s successfully created", doc.get("pileupName"))
        except errors.DuplicateKeyError:
            msg = f"Failed to insert: {doc}, it already exist in DB"
            self.logger.exception(msg)
            err = MSPileupDuplicateDocumentError(doc, msg)
            self.logger.error(err)
            return [err.error()]
        return []

    def updatePileup(self, doc):
        """
        Update pileup data with provided input

        :param doc: a dictionary of pieleup data to be updated
        :return: list of MSPileupError or empty list
        """
        # check if given document contains pileup Name (unique key)
        pname = doc.get('pileupName', '')
        if not pname:
            err = MSPileupNoKeyFoundError(doc, f'No document found for {pname}')
            self.logger.error(err)
            return [err.error()]

        # look-up piileup document in underlying DB
        spec = {'pileupName': pname}
        results = self.getPileup(spec)
        if not results:
            err = MSPileupNoKeyFoundError(spec, f'No document found for {spec} query')
            self.logger.error(err)
            return [err.error()]

        # we should have a single document corresponding to given pileup name
        if len(results) != 1:
            msg = f"Unique constrain violated for {pname}"
            err = MSPileupUniqueConstrainError(spec, msg)
            self.logger.error(err)
            return [err.error()]

        # we do not need to create MSPileupObj and validate it since our doc comes directly from DB
        doc['lastUpdateTime'] = gmtimeSeconds()
        try:
            self.dbColl.update_one(spec, {"$set": doc})
            self.logger.info("Pileup object %s successfully updated", spec.get("pileupName"))
        except Exception as exp:
            msg = f"Failed to insert: {doc}, error {exp}"
            self.logger.exception(msg)
            err = MSPileupDatabaseError(doc, msg, exp)
            self.logger.error(err)
            return [err.error()]
        return []

    def getPileup(self, spec, projection=None):
        """
        Fetch MSPileup data from persistent storage for a given spec (JSON query)

        :param spec: input MongoDB query (JSON spec)
        :param projection: MongoDB projection,
        see https://pymongo.readthedocs.io/en/stable/api/pymongo/collection.html
        :return: list of documents fetched from database
        """
        results = []

        for doc in self.dbColl.find(spec, projection):
            doc = stripKeys(doc, ['_id'])
            results.append(doc)
        return results

    def deletePileup(self, spec):
        """
        Delete MSPileup data in persistent storage for given spec (JSON query)

        :param spec: MongoDB spec (JSON query)
        :return: list of MSPileupError or empty list
        """
        try:
            self.dbColl.delete_one(spec)
            self.logger.info("Pileup object %s successfully deleted", spec.get("pileupName"))
        except Exception as exp:
            msg = f"Unable to delete with spec {spec}, error {exp}"
            self.logger.exception(msg)
            err = MSPileupDatabaseError(spec, msg)
            self.logger.error(err)
            return [err.error()]
        return []