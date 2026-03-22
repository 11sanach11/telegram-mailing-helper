from fastapi import APIRouter, Depends, HTTPException

from telegram_mailing_help.db.dao import User, UserState
from telegram_mailing_help.pwa.deps import get_current_pwa_user

router = APIRouter()


def _dao():
    from telegram_mailing_help.pwa import deps
    return deps._dao


def _prep():
    from telegram_mailing_help.pwa import deps
    return deps._prep


def _filter_group(telegram_id: str, group):
    """Mirrors bot.py group visibility logic based on show_group_only_for field."""
    show_only_for = group.show_group_only_for
    if not show_only_for:
        return True
    ids = [x.strip() for x in show_only_for.split(",") if x.strip()]
    positive = [x for x in ids if not x.startswith("-")]
    negative = [x[1:] for x in ids if x.startswith("-")]
    if negative and telegram_id in negative:
        return False
    if positive and telegram_id not in positive:
        return False
    return True


@router.get("/status")
def user_status(current_user: User = Depends(get_current_pwa_user)):
    return {
        "state": current_user.state,
        "name": current_user.name,
        "has_telegram": current_user.telegram_id is not None,
    }


@router.get("/groups")
def get_groups(current_user: User = Depends(get_current_pwa_user)):
    dao = _dao()
    tg_id = current_user.telegram_id or ""
    groups = list(dao.getEnabledDispatchGroupNames())
    visible = [g for g in groups if _filter_group(tg_id, g)]
    return [
        {
            "id": g.id,
            "name": g.dispatch_group_name,
            "description": g.description,
        }
        for g in visible
    ]


@router.post("/groups/{group_id}/assign")
def assign_block(group_id: int, current_user: User = Depends(get_current_pwa_user)):
    if current_user.state != UserState.CONFIRMED.value:
        raise HTTPException(
            status_code=403,
            detail="Ваш аккаунт ещё не подтверждён администратором"
        )
    prep = _prep()
    block_text, dispatch_list_id, already_assigned = prep.getAndAssignDispatchList(
        current_user, group_id
    )
    return {
        "block": block_text,
        "dispatch_list_id": dispatch_list_id,
        "already_assigned_count": already_assigned,
    }


@router.post("/groups/{group_id}/return/{dispatch_list_id}")
def return_block(
    group_id: int,
    dispatch_list_id: int,
    current_user: User = Depends(get_current_pwa_user),
):
    prep = _prep()
    result = prep.unassignDispatchListFromUser(current_user, dispatch_list_id)
    success = result is not None and not result.is_assigned
    return {"success": success}
