

import boto3
import json
import os
import pprint

pp = pprint.PrettyPrinter(indent=4)

# Initialize boto objects 
s3_resource = boto3.resource('s3')
s3_client = boto3.client('s3')
cf = boto3.client('cloudformation')
rds = boto3.client('rds')
# Initialize variables
bucket_name = os.environ['S3_BUCKET_NAME']
dir_name = os.environ['S3_DIR_NAME']
rds_metadata_obj_name = dir_name + '/' + os.environ['RDS_METADATA_FILENAME']
sns_arn = os.environ['SNS_ARN']
rds_tag_value = os.environ['RDS_TAG_VALUE']
s3_bucket = s3_resource.Bucket(bucket_name)

#def create_rds_stacks(event, context):
def create_rds_instances():

    # Get the previous RDS instance parameters from S3 as recorded by the delete process
    try:
        j = s3_client.get_object(Bucket=bucket_name, Key=rds_metadata_obj_name)['Body'].read()
    except Exception, err:
        print "ERROR: Error retreiving RDS instance metadata: %s" % err
        
    try:
        rds_instances_metadata = json.loads(j)
    except Exception, err:
        print "ERROR: Error converting S3 text file to dictionary: %s" % err
        
    # Find the CF templates used for each CF Stack,
    # then use the params for each stack to create 
    # each new stack
    for instance in rds_instances_metadata.keys():
        db_instance_name = instance.lower()
        db_instance_identifier = rds_instances_metadata[instance]['DBInstanceIdentifier'].lower()
        snapshot_id_partial = db_instance_name + '-lifecycle-snapshot-'
        #cf_template_partial = rds_instances_metadata[instance]['Template']

        # Get all of this DB instance's snapshots
        try:
            snapshots = rds.describe_db_snapshots(DBInstanceIdentifier=db_instance_identifier)
        except Exception, err:
            print "ERROR: Error retreiving %s snapshots metadata: %s" % (db_instance_identifier, err)

        # Loop through all of this DB instance's snapshots to find one that was
        # created by RDS.
        # The delete process should keep the most recent CF-created snapshot.
        for snapshot in snapshots['DBSnapshots']:
            if snapshot_id_partial in snapshot['DBSnapshotIdentifier']:
                db_snapshot_identifier = snapshot['DBSnapshotIdentifier']

        restore_kwargs = {
            'DBInstanceIdentifier': rds_instances_metadata[instance]['DBInstanceIdentifier'],
            'DBSnapshotIdentifier': db_snapshot_identifier,
            'DBInstanceClass': rds_instances_metadata[instance]['DBInstanceClass'],
            'AvailabilityZone': rds_instances_metadata[instance]['AvailabilityZone'],
            'DBSubnetGroupName': rds_instances_metadata[instance]['DBSubnetGroup']['DBSubnetGroupName'],
            'MultiAZ': rds_instances_metadata[instance]['MultiAZ'],
            'PubliclyAccessible': rds_instances_metadata[instance]['PubliclyAccessible'],
            'AutoMinorVersionUpgrade': rds_instances_metadata[instance]['AutoMinorVersionUpgrade'],
            'StorageType': rds_instances_metadata[instance]['StorageType'],
            'Tags': [
                        {
                            "Key": "AWSService",
                            "Value": rds_tag_value
                        }
                    ],
            'CopyTagsToSnapshot': True
        }

        # Create the new instance using the DB snapshot if it exists.
        # If snapshot doesn't exist create a new DB instance using the
        # parameters for that instance.

        response = False
        try:
            response = rds.restore_db_instance_from_db_snapshot(**restore_kwargs)
            print "NOTICE: Created DB Instance: %s from DB snapshot: %s" % (db_instance_name, db_snapshot_identifier)

        except Exception, err:
            print "ERROR: Error creating DB Instance %s: %s" % (db_instance_name, err)

create_rds_instances()