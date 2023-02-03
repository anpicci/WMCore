"""
File       : MSPileupObj.py
Author     : Valentin Kuznetsov <vkuznet AT gmail dot com>
Description: MSPileupObj module provides MSPileup data structure:

{
    "pileupName": string with the pileup dataset
    "pileupType": string with a constant value
    "insertTime": int, seconds since epoch in GMT timezone
    "lastUpdateTime": int, seconds since epoch in GMT timezone
    "expectedRSEs": ["Disk1", "Disk2", etc],  # these values need to be validated against Rucio
    "currentRSEs": ["Disk1", "Disk3"],  # values provided by the MS itself
    "fullReplicas": integer,  # total number of replicas to keep on Disk
    "campaigns": [ "name", ... ] # list of workflow campaigns using this pileup
    "containerFraction": real number with the container fraction to be distributed (TBFD)
    "replicationGrouping": string with a constant value (DATASET or ALL, to be in sync with Rucio)
    "activatedOn": int, seconds since epoch in GMT timezone
    "deactivatedOn": int, seconds since epoch in GMT timezone
    "active": boolean,
    "pileupSizeGB": integer, current size of the pileup in GB (integer)
    "rulesList: list of strings (rules) used to lock the pileup id
}

The data flow should be done via list of objects, e.g.
[<pileup object 1>, <pileup object 2>, ..., <pileup object n>]
"""

# system modules
import json

# WMCore modules
from WMCore.MicroService.Tools.Common import getMSLogger
from WMCore.Lexicon import dataset
from Utils.Timers import gmtimeSeconds


class MSPileupObj(object):
    """
    MSPileupObj defines MSPileup data stucture
    """
    def __init__(self, pdict, verbose=None, logger=None, validRSEs=None):
        self.logger = getMSLogger(verbose, logger)
        if not validRSEs:
            validRSEs = []
        self.validRSEs = validRSEs

        self.data = {
            'pileupName': pdict.get('pileupName', ''),
            'pileupType': pdict.get('pileupType', ''),
            'insertTime': pdict.get('insertTime', gmtimeSeconds()),
            'lastUpdateTime': pdict.get('lastUpdateTime', gmtimeSeconds()),
            'expectedRSEs': pdict.get('expectedRSEs', []),
            'currentRSEs': pdict.get('currentRSEs', []),
            'fullReplicas': pdict.get('fullReplicas', 0),
            'campaigns': pdict.get('campaigns', []),
            'containerFraction': pdict.get('containerFraction', 1.0),
            'replicationGrouping': pdict.get('replicationGrouping', ""),
            'activatedOn': pdict.get('activatedOn', gmtimeSeconds()),
            'deactivatedOn': pdict.get('deactivatedOn', gmtimeSeconds()),
            'active': pdict.get('active', False),
            'pileupSize': pdict.get('pileupSize', 0),
            'ruleList': pdict.get('ruleList', [])}
        valid, msg = self.validate(self.data)
        if not valid:
            msg = f'MSPileup input is invalid, {msg}'
            raise Exception(msg)

    def __str__(self):
        """
        Return human readable representation of pileup data
        """
        return json.dumps(self.data, indent=4)

    def getPileupData(self):
        """
        Get pileup data
        """
        return self.data

    def validate(self, pdict=None):
        """
        Validate data according to its schema. If data is not provided via
        input pdict parameter, the validate method will validate internal
        data object.

        :param pdict: input data dictionary (optional)
        :return: (boolean status, string message) result of validation
        """
        msg = ""
        if not pdict:
            pdict = self.data
        docSchema = self.schema()
        if set(pdict) != set(docSchema):
            pkeys = set(pdict.keys())
            skeys = set(docSchema.keys())
            msg = f"provided object {pkeys} keys are not equal to schema keys {skeys}"
            self.logger.error(msg)
            return False, msg
        for key, val in pdict.items():
            if key not in docSchema:
                msg = f"Failed to validate {key}, not found in {docSchema}"
                self.logger.error(msg)
                return False, msg
            _, stype = docSchema[key]  # expected data type for our key
            if not isinstance(val, stype):
                dtype = str(type(val))     # obtained data type of our value
                msg = f"Failed to validate: {key}, expect data-type {stype} got type {dtype}"
                self.logger.error(msg)
                return False, msg
            if key == 'pileupName':
                try:
                    dataset(val)
                except AssertionError:
                    msg = f"pileupName value {val} does not match dataset pattern"
                    self.logger.error(msg)
                    return False, msg
            if key == "pileupType" and val not in ['classic', 'premix']:
                msg = f"pileupType value {val} is neither of ['classic', 'premix']"
                self.logger.error(msg)
                return False, msg
            if key == 'replicationGrouping' and val not in ['DATASET', 'ALL']:
                msg = f"replicationGrouping value {val} is neither of ['DATASET', 'ALL']"
                self.logger.error(msg)
                return False, msg
            if key == 'containerFraction' and (val > 1 or val < 0):
                msg = f"containerFraction value {val} outside [0,1] range"
                self.logger.error(msg)
                return False, msg
            if (key == 'expectedRSEs' or key == 'currentRSEs') and not self.validateRSEs(val):
                msg = f"{key} value {val} is not in validRSEs {self.validRSEs}"
                self.logger.error(msg)
                return False, msg
        return True, msg

    def validateRSEs(self, rseList):
        """
        Validate given list of RSEs

        :param rseList: list of RSEs
        :return: boolean
        """
        if rseList == self.validRSEs:
            return True
        for rse in rseList:
            if rse not in self.validRSEs:
                return False
        return True

    def schema(self):
        """
        Return the data schema for a record in MongoDB.
        It's a dictionary where:
        - key is schema attribute name
        - a value is a tuple of (default value, expected data type)

        :return: a dictionary
        """
        doc = {'pileupName': ('', str),
               'pileupType': ('', str),
               'insertTime': (0, int),
               'lastUpdateTime': (0, int),
               'expectedRSEs': ([], list),
               'currentRSEs': ([], list),
               'fullReplicas': (0, int),
               'campaigns': ([], list),
               'containerFraction': (1.0, float),
               'replicationGrouping': ('', str),
               'activatedOn': (0, int),
               'deactivatedOn': (0, int),
               'active': (False, bool),
               'pileupSize': (0, int),
               'ruleList': ([], list)}
        return doc