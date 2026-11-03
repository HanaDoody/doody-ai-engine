"""Connection capture handler for the collection channel."""
from app.catalog import loader
from app.core import ari_updater, contact_unlocker, energy_controller, state_space
from app.schemas.collection import CaptureResponse
from app.schemas.mission import Contact
from app.schemas.rhythm import Reward
from app.schemas.state import ARIVector, Dudy


def _find_pin(pin_id: str) -> dict:
    for pin in loader.pins():
        if pin.get("pin_id") == pin_id:
            return pin
    raise ValueError(f"unknown pin_id: {pin_id}")


def _find_dudy(dudy_id: str) -> Dudy:
    for item in loader.dudy_templates():
        if item.get("id") == dudy_id:
            return Dudy(**item)
    raise ValueError(f"unknown dudy_id: {dudy_id}")


def capture(
    pin_id: str,
    current_ari: ARIVector,
    energy: int,
    current_collection_count: int = 0,
) -> CaptureResponse:
    """Apply a pin's connection delta and return capture rewards/unlocks.

    Unlock (symmetric with autonomy's signature-mission finish line): capturing the
    signature Dudy is the trigger, and the required count N is personalised by the
    onboarding connection level (state_space.connection_unlock_count). No ARI
    threshold. This capture counts as +1 toward N.
    """
    pin = _find_pin(pin_id)
    dudy = _find_dudy(pin["dudy_id"])
    eta = energy_controller.eta(energy)
    delta = ARIVector(
        rhythm=0.0,
        autonomy=0.0,
        connection=float(pin["delta_connection"]),
    )
    updated_ari, applied_delta = ari_updater.apply(current_ari, delta, eta)

    unlocked_contacts: list[Contact] = []
    if dudy.tier == "signature":
        needed = state_space.connection_unlock_count(current_ari.connection)
        if current_collection_count + 1 >= needed:
            unlocked_contacts = contact_unlocker.unlocked_for_axis("connection")

    reward = Reward(hana_money=int(loader.gate_config()["capture_reward_hana_money"]))
    return CaptureResponse(
        dudy=dudy,
        reward=reward,
        updated_ari=updated_ari,
        applied_delta=applied_delta,
        collected_dudy=[dudy],
        unlocked_contacts=unlocked_contacts,
    )
