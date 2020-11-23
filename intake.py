# -*- coding: utf-8 -*-
"""Functions for revision management."""

__copyright__ = 'Copyright (c) 2019-2020, Utrecht University'
__license__   = 'GPLv3, see LICENSE'

import os
import time
import irods_types
import re

from rules_uu.util import *
from rules_uu.util.query import Query
from rules_uu.folder import *

__all__ = ['api_intake_list_studies',
           'api_intake_list_dm_studies',
           'api_intake_count_total_files',
           'api_intake_list_unrecognized_files',
           'api_intake_list_datasets',
           'api_intake_scan_for_datasets',
           'api_intake_lock_dataset',
           'api_intake_unlock_dataset',
           'api_intake_dataset_get_details',
           'api_intake_dataset_add_comment',
           'api_intake_report_vault_dataset_counts_per_study',
           'api_intake_report_vault_aggregated_info',
           'api_intake_report_export_study_data']


@api.make()
def api_intake_list_studies(ctx):
    """
    Get list of all studies current user is involved in
    """
    groups = []
    user_name = user.name(ctx)
    user_zone = user.zone(ctx)

    iter = genquery.row_iterator(
        "USER_GROUP_NAME",
        "USER_NAME = '" + user_name + "' AND USER_ZONE = '" + user_zone + "'",
        genquery.AS_LIST, ctx
    )

    for row in iter:
        if row[0].startswith('grp-intake-'):
            groups.append(row[0][11:])

    groups.sort()
    return groups


@api.make()
def api_intake_list_dm_studies(ctx):
    """ Return list of studies current user is datamanager of """
    datamanager_groups = []
    user_name = user.name(ctx)
    user_zone = user.zone(ctx)

    iter = genquery.row_iterator(
        "USER_GROUP_NAME",
        "USER_NAME = '" + user_name + "' AND USER_ZONE = '" + user_zone + "'",
        genquery.AS_LIST, ctx
    )

    for row in iter:
        if row[0].startswith('grp-intake-'):
            study = row[0][11:]
            # Is a member of this study ... check whether member of corresponding datamanager group
            iter2 = genquery.row_iterator(
                "USER_NAME",
                "USER_TYPE = 'rodsgroup' AND USER_NAME like 'datamanager-" + study + "'",
                genquery.AS_LIST, ctx
            )
            for row2 in iter2:
                datamanager_group = row2[0]
                if user.is_member_of(ctx, datamanager_group): 
                    datamanager_groups.append(study)

    return datamanager_groups


@api.make()
def api_intake_count_total_files(ctx, coll):
    """ get the total count of all files in coll """

    log.write(ctx, coll)
    # Include coll name as equal names do occur and genquery delivers distinct results.
    iter = genquery.row_iterator(
        "COLL_NAME, DATA_NAME",
        "COLL_NAME like '" + coll + "%'",
        genquery.AS_LIST, ctx
    )

    count = 0
    for row in iter:
        log.write(ctx, row[0] + '/' + row[1])
        count += 1

    log.write(ctx, str(count))
        
    return count



@api.make()
def api_intake_list_unrecognized_files(ctx, coll):
    """
    Get list of all unrecognized files for given path including relevant metadata

    :param coll: collection to find unrecognized and unscanned files in
    """
    log.write(ctx, coll)
    # Include coll name as equal names do occur and genquery delivers distinct results.
    iter = genquery.row_iterator(
        "COLL_NAME, DATA_NAME, COLL_CREATE_TIME, DATA_OWNER_NAME",
        "COLL_NAME like '" + coll + "%' AND META_DATA_ATTR_NAME = 'unrecognized'",
        genquery.AS_LIST, ctx
    )

    files = []
    for row in iter:
        # Error is hardcoded! (like in the original) and initialize attributes already as empty strings.
        file_data = {"name": row[1],
                     "path": row[0],
                     "date": row[2],
                     "creator": row[3],
                     "error": 'Experiment type, wave or pseudocode is missing from path',
                     "experiment_type": '',
                     "pseudocode": '',
                     "wave": '',
                     "version": ''
        }
        # per data object get relevent metadata (experiment type, version, wave, pseudocode) if present
        iter2 = genquery.row_iterator(
            "META_DATA_ATTR_NAME, META_DATA_ATTR_VALUE",
            "COLL_NAME = '" + row[0] + "' AND DATA_NAME = '" + row[1] +"' AND META_DATA_ATTR_NAME in ('experiment_type', 'pseudocode', 'wave', 'version')",
            genquery.AS_LIST, ctx
        )
        for row2 in iter2:
            log.write(ctx, row2[0])
            file_data[row2[0]] = row2[1]

        files.append(file_data) 

    return files


@api.make()
def api_intake_list_datasets(ctx, coll):
    """
    Get list of datasets for given path.
    A dataset is distinguished by attribute name 'dataset_toplevel' which can either reside on a collection or a data object.
    That is why 2 seperate queries have to be performed.
    :param coll: collection from which to list all datasets
    """
    
    datasets = []
    
    """
    dataset = {}
    
    dataset['dataset_id'] = '123455'
    dataset['path'] = coll
    dataset['wave'] = '1'
    dataset['expType'] = '2'   ### DIT MOET experiment_type worden voor gemak en consistentie
    dataset['pseudocode'] = '3'
    dataset['version'] = '4'
    dataset['datasetStatus'] = 'locked'
    dataset['datasetCreateName'] = 'locked'
    dataset['datasetCreateDate'] = 0
    dataset['datasetErrors'] = 0
    dataset['datasetWarnings'] = 0
    dataset['datasetComments'] = 0
    dataset['objects'] = 5
    dataset['objectErrors'] = 0
    dataset['objectWarnings'] = 0

    datasets.append(dataset)

    dataset = {}
    dataset['dataset_id'] = '22123455'
    dataset['path'] = coll + 'blabla'
    dataset['wave'] = '1'
    dataset['expType'] = '2'   ### DIT MOET experiment_type worden voor gemak en consistentie
    dataset['pseudocode'] = '3'
    dataset['version'] = '4'
    dataset['datasetStatus'] = 'locked'
    dataset['datasetCreateName'] = 'locked'
    dataset['datasetCreateDate'] = 0
    dataset['datasetErrors'] = 0
    dataset['datasetWarnings'] = 0
    dataset['datasetComments'] = 0
    dataset['objects'] = 10
    dataset['objectErrors'] = 0
    dataset['objectWarnings'] = 0
    
    datasets.append(dataset)

    dataset = {}

    dataset['dataset_id'] = '123455'
    dataset['path'] = coll
    dataset['wave'] = '1'
    dataset['expType'] = '2'   ### DIT MOET experiment_type worden voor gemak en consistentie
    dataset['pseudocode'] = '3'
    dataset['version'] = '4'
    dataset['datasetStatus'] = 'frozen'
    dataset['datasetCreateName'] = 'frozen'
    dataset['datasetCreateDate'] = 0
    dataset['datasetErrors'] = 0
    dataset['datasetWarnings'] = 0
    dataset['datasetComments'] = 0
    dataset['objects'] = 5
    dataset['objectErrors'] = 0
    dataset['objectWarnings'] = 0

    datasets.append(dataset)

    return datasets
    """
    

    log.write(ctx, coll)


    # 1) Query for datasets distinguished by collections
#      "COL_META_COLL_ATTR_VALUE" => NULL,
#      "COL_COLL_NAME" => NULL
#        $condition->add('COL_COLL_NAME', 'like', $referencePath . '%');
#        $condition->add('COL_META_COLL_ATTR_NAME', '=', 'dataset_toplevel');

    iter = genquery.row_iterator(
        "META_COLL_ATTR_VALUE, COLL_NAME",
        "COLL_NAME like '" + coll + "%' AND META_COLL_ATTR_NAME = 'dataset_toplevel' ", 
        genquery.AS_LIST, ctx
    )
    for row in iter:
        log.write(ctx, 'DATASET COLL: ' + row[1])
        dataset = get_dataset_details(ctx, row[0], row[1])
        datasets.append(dataset)


    # 2) Query for datasets distinguished dataobjects
#    "COL_META_DATA_ATTR_VALUE" => NULL,
#     "COL_COLL_NAME" => NULL,
#    $condition->add('COL_COLL_NAME', 'like', $referencePath . '/%');
#    $condition->add('COL_META_DATA_ATTR_NAME', '=', 'dataset_toplevel');

    iter = genquery.row_iterator(
        "META_DATA_ATTR_VALUE, COLL_NAME",
        "COLL_NAME like '" + coll + "%' AND META_DATA_ATTR_NAME = 'dataset_toplevel' ",
        genquery.AS_LIST, ctx
    )
    for row in iter:
        log.write(ctx, 'DATASET DATA: ' + row[1])
        dataset = get_dataset_details(ctx, row[0], row[1])
        datasets.append(dataset)

    # 3) extra query for datasets that fall out of above query due to 'like' in query
#    "COL_META_DATA_ATTR_VALUE" => NULL,
#    "COL_COLL_NAME" => NULL,
#    $condition->add('COL_COLL_NAME', '=', $referencePath);
#    $condition->add('COL_META_DATA_ATTR_NAME', '=', 'dataset_toplevel');

    iter = genquery.row_iterator(
        "META_DATA_ATTR_VALUE, COLL_NAME",
        "COLL_NAME = '" + coll + "' AND META_DATA_ATTR_NAME = 'dataset_toplevel' ",
        genquery.AS_LIST, ctx
    )
    for row in iter:
        log.write(ctx, 'DATASET DATA2: ' + row[1])
        dataset = get_dataset_details(ctx, row[0], row[1])
        datasets.append(dataset)

    return datasets


def get_dataset_details(ctx, dataset_id, path):
    """ get details of dataset based on dataset_id (dataset['dataset_id'])
    :param dataset_id    id of dataset
    :param path          path to dataset
    """
    # Inialise all attributes
    dataset = {"dataset_id": dataset_id,
               "path": path
    }

    # uuYcDatasetParseId(*id, *idComponents){
    #    *idParts = split(*id, "\t");
    #    *idComponents."wave"            = elem(*idParts, 0);
    #    *idComponents."experiment_type" = elem(*idParts, 1);
    #    *idComponents."pseudocode"      = elem(*idParts, 2);
    #    *idComponents."version"         = elem(*idParts, 3);
    #    *idComponents."directory"       = elem(*idParts, 4);

    # Parse dataset_id to get WEPV-items individually
    dataset_parts = dataset_id.split('\t')
    dataset['wave'] = dataset_parts[0]
    dataset['expType'] = dataset_parts[1]
    dataset['experiment_type'] = dataset_parts[1]
    dataset['pseudocode'] = dataset_parts[2]
    dataset['version'] = dataset_parts[3]
    directory = dataset_parts[4] # HIER WORDT NIKS MEE GEDAAN - toch ff zo laten

    dataset['datasetStatus'] = 'scanned'
    dataset['datasetCreateName'] = '==UNKNOWN=='
    dataset['datasetCreateDate'] = 0
    dataset['datasetErrors'] = 0
    dataset['datasetWarnings'] = 0
    dataset['datasetComments'] = 0
    dataset['objects'] = 0
    dataset['objectErrors'] = 0
    dataset['objectWarnings'] = 0

    tl_info = get_dataset_toplevel_objects(ctx, path, dataset_id)
    is_collection = tl_info['is_collection']
    tl_objects = tl_info['objects']

    if is_collection:
        """ dataset is based on a collection """
        tl_collection = tl_objects[0]
        iter = genquery.row_iterator(
            "COLL_NAME, COLL_OWNER_NAME, COLL_CREATE_TIME",
            "COLL_NAME = '" + tl_collection + "' ",
            genquery.AS_LIST, ctx
        )
        for row in iter:
            dataset['datasetCreateName'] = row[1]
            dataset['datasetCreateDate'] = row[2]

        iter = genquery.row_iterator(
            "COLL_NAME, META_COLL_ATTR_NAME, count(META_COLL_ATTR_VALUE)",
            "COLL_NAME = '" + tl_collection + "' ",
            genquery.AS_LIST, ctx
        )
        for row in iter:
            if row[1] == 'dataset_error':
                dataset['datasetErrors'] += int(row[2])
            if row[1] == 'dataset_warning':
                dataset['datasetWarnings'] += int(row[2])
            if row[1] == 'comment':
                dataset['datasetComments'] += int(row[2])
            if row[1] == 'to_vault_freeze':
                dataset['datasetStatus'] = 'frozen'
            if row[1] == 'to_vault_lock':
                dataset['datasetStatus'] = 'locked'

        iter = genquery.row_iterator(
            "COLL_NAME, META_COLL_ATTR_NAME, META_COLL_ATTR_VALUE",
            "COLL_NAME = '" + tl_collection + "' ",
            genquery.AS_LIST, ctx
        )
        for row in iter:
            if row[1] == 'object_count':
                dataset['objects'] += int(row[2])
            if row[1] == 'object_errors':
                dataset['objectErrors'] += int(row[2])
            if row[1] == 'object_warnings':
               dataset['objectWarnings'] += int(row[2])
    else:
        """ dataset is based on a dataobject
        Step through all data objects as found in tlObjects """
        objects = 0
        object_errors = 0
        object_warnings = 0
        for tl_object in tl_objects:

            # split tl_object
            log.write(ctx, tl_object)
            tlo = pathutil.chop(tl_object)
            log.write(ctx, tlo)
            parent = tlo[0]
            base_name = tlo[1]

            objects += 1
            if objects == 1:
                iter = genquery.row_iterator(
                    "DATA_OWNER_NAME, DATA_CREATE_TIME",
                    "COLL_NAME = '" +  parent + "' and DATA_NAME = '" + base_name + "' ",
                    genquery.AS_LIST, ctx
                )
                for row in iter:
                    dataset['datasetCreateName'] = row[0]
                    dataset['datasetCreateDate'] = row[1]

            iter = genquery.row_iterator(
                "META_DATA_ATTR_NAME, META_DATA_ATTR_VALUE",
                "COLL_NAME = '" +  parent + "' and DATA_NAME = '" + base_name + "' ",
                genquery.AS_LIST, ctx
            )
            for row in iter:
                if row[0] == 'error':
                    object_errors += 1
                if row[0] == 'warning':
                    object_warnings += 1
                if objects == 1:
                    # Only look at these items when objects==1 as they are added to each toplevel object present
                    if row[0] == 'dataset_error':
                        dataset['datasetErrors'] += 1
                    if row[0] == 'dataset_warning':
                        dataset['datasetWarnings'] += 1
                    if row[0] == 'comment':
                        dataset['datasetComments'] += 1
                if row[0] == 'to_vault_freeze':
                    dataset['datasetStatus'] = 'frozen'
                if row[0] == 'to_vault_lock':
                    dataset['datasetStatus'] = 'locked'
        ## HDR-klopt dit??
        dataset['objects'] = objects
        dataset['objectErrors'] = object_errors
        dataset['objectWarnings'] = object_warnings

    return dataset


def get_dataset_toplevel_objects(ctx, root, dataset_id):
    """ returns dict with toplevel object paths and whether is collection based dataset 
    if is a collection - only one object is returned (collection path)
    if not a collection- all objects are returned with full object path

    :param root - path to a dataset
    :dataset_id - id of the dataset
    """
    log.write(ctx, '****************** IN GET DATASET TOPLEVEL')
    log.write(ctx, root)
    log.write(ctx, dataset_id)
    iter = genquery.row_iterator(
        "COLL_NAME",
        "COLL_NAME LIKE '" + root + "%' AND META_COLL_ATTR_NAME = 'dataset_toplevel' "
        "AND META_COLL_ATTR_VALUE = '" + dataset_id + "'",
        genquery.AS_LIST, ctx
    )
    for row in iter:
        return {'is_collection': True,
                'objects': [row[0]]}

    # For dataobject situation gather all object path strings as a list
    iter = genquery.row_iterator(
        "DATA_NAME, COLL_NAME",
        "COLL_NAME like '" + root + "%' AND META_DATA_ATTR_NAME = 'dataset_toplevel' "
        "AND META_DATA_ATTR_VALUE = '" + dataset_id + "'",
        genquery.AS_LIST, ctx
    )
    objects = []
    for row in iter:
        objects.append(row[1] + '/' + row[0])
    return {'is_collection': False,
            'objects': objects}


@api.make()
def api_intake_scan_for_datasets(ctx, coll):
    """ The toplevel of a dataset can be determined by attribute 'dataset_toplevel' and can either be a collection or a data_object
    :param coll: collection to scan for datasets
    """

    # folder.set_status(coll, 'lock')
   
    # The dataset collection, or the first parent of a data-object dataset object.
    # Incorporated into the dataset_id.
    # *scope."dataset_directory"    = ".";

    # Extracted WEPV, as found in pathname components.
    # *scope."wave"            = ".";
    # *scope."experiment_type" = ".";
    # *scope."pseudocode"      = ".";
    # *scope."version"         = ".";
   
    # MOET DIT ECHT!!?? 
    scope = {"wave": "",
             "experiment_type": "",
             "preudocode": ""}
             # "version": "."}

    log.write(ctx, "BEFORE SCAN coll: " + coll)

    intake_scan_collection(ctx, coll, scope, False)

    log.write(ctx, "AFTER SCAN")
    log.write(ctx, "BEFORE CHECK")
    
    intake_check_datasets(ctx, coll)

    log.write(ctx, "AFTER CHECK")
    log.write(ctx, "TOTALLY FINISHED ***********************************************")

    return {"proc_status": "OK"}

    # folder.set_status(coll, 'unlocked')


@api.make()
def api_intake_lock_dataset(ctx, path, dataset_id):
    """
    Lock a dataset to mark as an indication it can be 'frozen' for it to progress to vault
    Lock = datamanager only
    :param coll: collection for which to lock a specific dataset id
    :param dataset_id: id of the dataset to be locked
    """
    intake_dataset_lock(ctx, path, dataset_id)

    return 'OK'


@api.make()
def api_intake_unlock_dataset(ctx, path, dataset_id):
    """
    Unlock a dataset to remove the indication so it can be 'frozen' for it to progress to vault
    Unlock = datamanager only
    :param coll: collection for which to lock a specific dataset id
    :param dataset_id: id of the dataset to be unlocked
    """
    intake_dataset_unlock(ctx, path, dataset_id)

    return 'OK'


@api.make()
def api_intake_dataset_add_comment(ctx, coll, dataset_id, comment):
    """ Add a comment to a dataset
    :param coll
    :param dataset_id: id of the dataset to add a comment to
    :param comment comment as added by user
    """
    # Authorisation still to be added. Or NOT? As irods will interfere?

    tl_info = get_dataset_toplevel_objects(ctx, coll, dataset_id)
    is_collection = tl_info['is_collection']
    tl_objects = tl_info['objects'] 

    timestamp = int(time.time()) # int(datetime.timestamp(datetime.now()))

    comment_data = user.name(ctx) + ':' + str(timestamp) + ':' + comment

    for tl in tl_objects:
        if is_collection:
            avu.associate_to_coll(ctx, tl, 'comment', comment_data)
        else:
            avu.associate_to_data(ctx, tl, 'comment', comment_data)

    return 'COMMENT OK'



@api.make()
def api_intake_dataset_get_details(ctx, coll, dataset_id):
    """
    Get all details for a dataset (errors/warnings, scanned by who/when, comments, file tree)
    1) Errors/warnings
    2) Comments
    3) Tree view of files within dataset.
    :param dataset_id: id of the dataset to get details for
    """

    tl_info = get_dataset_toplevel_objects(ctx, coll, dataset_id)
    is_collection = tl_info['is_collection']
    tl_objects = tl_info['objects']

    # return tl_objects

    comments = []
    for tl in tl_objects:
        if is_collection:
            iter = genquery.row_iterator(
                "META_COLL_ATTR_VALUE, order_desc(META_COLL_MODIFY_TIME)",
                "META_COLL_ATTR_NAME = 'comment' AND COLL_NAME = '{}'".format(coll),
                genquery.AS_LIST, ctx
            )
            for row in iter:
                comments.append(row[0])

    return comments

    # 'scanned'
    # 'dataset_warning'
    # 'dataset_error'


# Reporting / export functions
@api.make()
def  api_intake_report_vault_dataset_counts_per_study(ctx, study_id):
    """
    Get the count of datasets wave/experimenttype
    In the vault a dataset is always located in a folder.
    Therefore, looking at the folders only is enough
    :param study_id: id of the study involved
    """
    log.write(ctx, 'ERIN')
    return intake_youth_dataset_counts_per_study(ctx, study_id)

    # return 'vault dataset counts per study' + study_id


@api.make()
def  api_intake_report_vault_aggregated_info(ctx, study_id):
    """
    Collects the following information for Raw, Processed datasets. Including a totalisation of this all
    (Raw/processed is kept in VERSION)

    -Total datasets
    -Total files
    -Total file size
    -File size growth in a month
    -Datasets growth in a month
    -Pseudocodes  (distinct)
    :param study_id: id of the study involved
    """

    log.write(ctx, 'ERIN VAULT AGGREGATED INFO')
    return vault_aggregated_info(ctx, study_id)


@api.make()
def api_intake_report_export_study_data(ctx, study_id):
    """
    Find all datasets in the vault for $studyID.
    Include file count and total file size as well as dataset meta data version, experiment type, pseudocode and wave
    :param study_id: id of the study involved
    """
    return intake_report_export_study_data(ctx, study_id)

