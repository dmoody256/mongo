// Cannot implicitly shard accessed collections because of collection existing when none
// expected.
// @tags: [
//   assumes_no_implicit_collection_creation_after_drop,
//   requires_collstats,
//   uses_multiple_connections,
//   requires_fcv_50,
// ]

var isDotsAndDollarsEnabled = db.adminCommand({getParameter: 1, featureFlagDotsAndDollars: 1})
                                  .featureFlagDotsAndDollars.value;
if (!isDotsAndDollarsEnabled) {
    // Create a new connection object so it won't affect the global connection when we modify
    // it's settings.
    var conn = new Mongo(db.getMongo().host);

    t = conn.getDB(db.getName()).insert2;
    t.drop();

    assert.isnull(t.findOne(), "A");
    assert.writeError(t.insert({z: 1, $inc: {x: 1}}, 0, true));
    assert.isnull(t.findOne(), "B");
    // Collection should not exist
    assert.isnull(t.exists());
}