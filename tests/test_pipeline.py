FORWARD = {"FWD-A", "FWD-B"}
NETWORK = {"FWD-A", "FWD-B", "STORAGE"}


def test_pipeline_runs_and_master_complete(state):
    cat_ids = set(state.catalog["items"].item_id)
    assert len(state.master) == len(cat_ids)
    assert set(state.master.item_id) == cat_ids
    for col in ["bucket", "abc", "min_qty", "placement_class", "primary_home", "has_policy"]:
        assert col in state.master.columns
    assert state.master["primary_home"].notna().all()


def test_shared_item_ids_across_stages(state):
    ids = set(state.catalog["items"].item_id)
    assert set(state.forecast.item_id) == ids
    assert set(state.classification.item_id) == ids
    assert set(state.policy.item_id) == ids
    assert set(state.home["table"].item_id) == ids


def test_one_shared_network(state):
    assert set(state.catalog["network"].building) == NETWORK
    assert set(state.home["table"].primary_home) <= NETWORK


def test_never_sold_is_new_and_forward(state):
    m = state.master
    new = m[m["never_sold"]]
    assert len(new) > 0
    assert (new["placement_class"] == "new").all()
    assert new["primary_home"].isin(FORWARD).all()      # provisional forward, never storage
    assert new["has_policy"].all()


def test_dead_stock_parked_in_storage(state):
    dead_ids = set(state.catalog["items"].query("lifecycle == 'dead'").item_id)
    m = state.master.set_index("item_id")
    parked = m.loc[list(dead_ids)]
    assert (parked["placement_class"] == "dead").all()
    assert (parked["primary_home"] == "STORAGE").all()
    assert (~parked["has_policy"]).all()


def test_forward_items_have_policy_storage_tail_does_not(state):
    m = state.master
    assert m[m["primary_home"].isin(FORWARD)]["has_policy"].all()
    assert (~m[m["primary_home"] == "STORAGE"]["has_policy"]).all()


def test_container_routes_only_forward_items(state):
    ci = state.container["data"]["items"]
    assert ci["home"].isin(FORWARD).all()
    fwd_ids = set(state.home["table"].query("primary_home in @FORWARD").item_id)
    assert set(ci.item_id) <= fwd_ids


def test_container_etas_feed_transfer(state):
    inbound = state.container["inbound"]
    assert len(inbound) > 0
    for e in inbound[:5]:
        assert e["to_loc"] in FORWARD and e["eta"] >= 0


def test_transfer_operates_on_forward_items(state):
    fwd_ids = set(state.home["table"].query("primary_home in @FORWARD").item_id)
    tr_ids = set(state.transfer["state"]["items"].item_id)
    assert tr_ids <= fwd_ids
    assert state.transfer["result"]["used"] >= 0


def test_home_footprint_uses_policy_ophq(state):
    # forward items are sized from the policy engine's OPHQ, so footprint is positive
    t = state.home["table"]
    fwd = t[t["primary_home"].isin(FORWARD)]
    assert (fwd["footprint"] > 0).all()
