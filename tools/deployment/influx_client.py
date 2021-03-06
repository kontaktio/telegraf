from influxdb import InfluxDBClient
from influxdb.exceptions import InfluxDBClientError


class InfluxClient:
    READ_PRIVILEGE = 'read'
    TELEMETRY_CQ_FMT = """
CREATE CONTINUOUS QUERY "telemetry_{0}_cq" ON "{4}"
RESAMPLE EVERY {3}
BEGIN
    SELECT 
        mean("batteryLevel") AS "batteryLevel", 
        mean("lightLevel") AS "lightLevel", 
        mean("rssi") AS "rssi", 
        mean("sensitivity") AS "sensitivity", 
        sum("singleClick") AS "singleClick", 
        sum("threshold") AS "threshold", 
        sum("doubleTap") AS "doubleTap", 
        mean("temperature") AS "temperature", 
        mean("humidity") as "humidity",
        mean("x") AS "x", 
        mean("y") AS "y", 
        mean("z") AS "z",
        max("history") AS "history",
        MODE("sourceId") AS "sourceId"
    INTO 
        "{1}"."telemetry_{0}"
    FROM 
       "{2}"."telemetry"
    GROUP BY time({0}), trackingId
END
"""

    LOCATION_CQ_FMT = """
CREATE CONTINUOUS QUERY "locations_{0}_cq" ON "{4}"
RESAMPLE EVERY {3} FOR {5}
BEGIN
    SELECT 
        mean("rssi") AS "rssi",
        COUNT("rssi") AS "scans",
        COUNT("rssi")/(-mean("rssi")) as "quality",
        MODE("fSourceId") AS "fSourceId",
        MODE("fTrackingId") AS "fTrackingId"
    INTO 
        "{1}"."locations_{0}"
    FROM 
       "{2}"."locations"
    GROUP BY time({0}), trackingId, sourceId
END
"""

    POSTIION_CQ_FMT = """
CREATE CONTINUOUS QUERY "positions_{0}_cq" ON "{4}"
RESAMPLE EVERY {3} 
BEGIN
    SELECT 
        mean("coord_latitude") AS "coord_latitude",
        mean("coord_longitude") AS "coord_longitude"        
    INTO 
        "{1}"."positions_{0}"
    FROM 
       current_rp.position
    GROUP BY time({0}), trackingId
END
"""

    REMOVE_CQ_FMT = """
DROP CONTINUOUS QUERY "{0}_{1}_cq" ON "{2}"
    """

    def __init__(self, address, port, user_name, password):
        self._client = InfluxDBClient(
            host=address.replace('http://', ''),
            port=port,
            username=user_name, 
            password=password)

    def create_database(self, database_name):
        print "Creating database %s" % database_name
        self._client.create_database(database_name)
        
    def create_user(self, user_name, password, database_name=None):
        print "Creating user %s" % user_name
        try:
            self._client.create_user(user_name, password)
        except InfluxDBClientError as e:
            if e.message != 'user already exists':
                raise e

        if database_name is not None:
            self._client.grant_privilege(self.READ_PRIVILEGE, database_name, user_name)

    def create_retention_policy(self, database_name, policy_name, duration):
        print "Creating retention policy %s with duration %s on database %s" % (policy_name, duration, database_name)
        try:
            self._client.create_retention_policy(policy_name, duration, 1, database=database_name)
        except InfluxDBClientError as e:
            if e.message == 'retention policy already exists':
                print "Updating retention policy %s with duration %s on database %s" % (policy_name, duration, database_name)
                self._client.alter_retention_policy(policy_name, database_name, duration, 1)

    def recreate_continuous_query(self, database_name, aggregation_time, retention_policy, source_retention_policy, resample_time, resample_for):
        self._execute_query(self.REMOVE_CQ_FMT.format(
            'telemetry',
            aggregation_time,
            database_name), 
            database_name)

        self._execute_query(self.REMOVE_CQ_FMT.format(
            'locations',
            aggregation_time,
            database_name),
            database_name)

        self._execute_query(self.REMOVE_CQ_FMT.format(
            'positions',
            aggregation_time,
            database_name),
            database_name)

        self._execute_query(self.TELEMETRY_CQ_FMT.format(
            aggregation_time, 
            retention_policy, 
            source_retention_policy, 
            resample_time, 
            database_name), 
            database_name)

        self._execute_query(self.LOCATION_CQ_FMT.format(
            aggregation_time,
            retention_policy,
            source_retention_policy,
            resample_time,
            database_name,
            resample_for),
            database_name)

        self._execute_query(self.POSTIION_CQ_FMT.format(
            aggregation_time,
            retention_policy,
            source_retention_policy,
            resample_time,
            database_name),
            database_name)

    def _execute_query(self, query, database_name):
        print "Executing query %s" % query
        self._client.query(query, database=database_name)
    
