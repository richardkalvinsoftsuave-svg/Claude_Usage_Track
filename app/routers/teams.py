"""Org hierarchy CRUD endpoints — managers, teams, team members."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Manager, Team, TeamMember
from app.schemas import (
    ManagerCreate,
    ManagerRead,
    ManagerUpdate,
    TeamCreate,
    TeamRead,
    TeamUpdate,
    TeamMemberCreate,
    TeamMemberRead,
    TeamMemberUpdate,
)

router = APIRouter()


# ── Managers ─────────────────────────────────────────────────────

@router.get("/managers", response_model=List[ManagerRead])
def list_managers(db: Session = Depends(get_db)) -> List[ManagerRead]:
    """List all managers, sorted by name."""
    items = db.query(Manager).order_by(Manager.name.asc()).all()
    return [ManagerRead.model_validate(m) for m in items]


@router.post("/managers", response_model=ManagerRead, status_code=status.HTTP_201_CREATED)
def create_manager(payload: ManagerCreate, db: Session = Depends(get_db)) -> ManagerRead:
    """Create a new manager."""
    existing = db.query(Manager).filter(Manager.name == payload.name.strip()).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Manager already exists")
    mgr = Manager(name=payload.name.strip())
    db.add(mgr)
    db.commit()
    db.refresh(mgr)
    return ManagerRead.model_validate(mgr)


@router.put("/managers/{manager_id}", response_model=ManagerRead)
def update_manager(manager_id: int, payload: ManagerUpdate, db: Session = Depends(get_db)) -> ManagerRead:
    """Update a manager's name."""
    mgr = db.query(Manager).filter(Manager.id == manager_id).first()
    if not mgr:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Manager not found")
    existing = db.query(Manager).filter(Manager.name == payload.name.strip(), Manager.id != manager_id).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Another manager has this name")
    mgr.name = payload.name.strip()
    db.commit()
    db.refresh(mgr)
    return ManagerRead.model_validate(mgr)


@router.delete("/managers/{manager_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_manager(manager_id: int, db: Session = Depends(get_db)):
    """Delete a manager and all their teams/members (cascade)."""
    mgr = db.query(Manager).filter(Manager.id == manager_id).first()
    if not mgr:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Manager not found")
    db.delete(mgr)
    db.commit()


# ── Teams ────────────────────────────────────────────────────────

@router.get("/teams", response_model=List[TeamRead])
def list_teams(
    manager_id: Optional[int] = Query(None, description="Filter by manager"),
    db: Session = Depends(get_db),
) -> List[TeamRead]:
    """List teams, optionally filtered by manager."""
    q = db.query(Team)
    if manager_id is not None:
        q = q.filter(Team.manager_id == manager_id)
    items = q.order_by(Team.name.asc()).all()
    return [TeamRead.model_validate(t) for t in items]


@router.post("/teams", response_model=TeamRead, status_code=status.HTTP_201_CREATED)
def create_team(payload: TeamCreate, db: Session = Depends(get_db)) -> TeamRead:
    """Create a new team under a manager."""
    mgr = db.query(Manager).filter(Manager.id == payload.manager_id).first()
    if not mgr:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Manager not found")

    existing = db.query(Team).filter(Team.name == payload.name.strip()).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Team already exists")

    t = Team(name=payload.name.strip(), manager_id=payload.manager_id)
    db.add(t)
    db.commit()
    db.refresh(t)
    return TeamRead.model_validate(t)


@router.put("/teams/{team_id}", response_model=TeamRead)
def update_team(team_id: int, payload: TeamUpdate, db: Session = Depends(get_db)) -> TeamRead:
    """Update a team's name and/or manager."""
    t = db.query(Team).filter(Team.id == team_id).first()
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    if payload.name is not None:
        existing = db.query(Team).filter(
            Team.name == payload.name.strip(), Team.id != team_id
        ).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Another team has this name")
        t.name = payload.name.strip()

    if payload.manager_id is not None:
        mgr = db.query(Manager).filter(Manager.id == payload.manager_id).first()
        if not mgr:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Manager not found")
        t.manager_id = payload.manager_id

    db.commit()
    db.refresh(t)
    return TeamRead.model_validate(t)


@router.delete("/teams/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_team(team_id: int, db: Session = Depends(get_db)):
    """Delete a team and all its members (cascade)."""
    t = db.query(Team).filter(Team.id == team_id).first()
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    db.delete(t)
    db.commit()


# ── Team Members ─────────────────────────────────────────────────

@router.get("/team-members", response_model=List[TeamMemberRead])
def list_team_members(
    team_id: Optional[int] = Query(None, description="Filter by team"),
    db: Session = Depends(get_db),
) -> List[TeamMemberRead]:
    """List team members, optionally filtered by team."""
    q = db.query(TeamMember)
    if team_id is not None:
        q = q.filter(TeamMember.team_id == team_id)
    items = q.order_by(TeamMember.name.asc()).all()
    return [TeamMemberRead.model_validate(tm) for tm in items]


@router.post("/team-members", response_model=TeamMemberRead, status_code=status.HTTP_201_CREATED)
def create_team_member(payload: TeamMemberCreate, db: Session = Depends(get_db)) -> TeamMemberRead:
    """Create a new team member under a team."""
    t = db.query(Team).filter(Team.id == payload.team_id).first()
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    existing = db.query(TeamMember).filter(TeamMember.name == payload.name.strip()).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Team member already exists")

    tm = TeamMember(name=payload.name.strip(), team_id=payload.team_id)
    db.add(tm)
    db.commit()
    db.refresh(tm)
    return TeamMemberRead.model_validate(tm)


@router.put("/team-members/{team_member_id}", response_model=TeamMemberRead)
def update_team_member(team_member_id: int, payload: TeamMemberUpdate, db: Session = Depends(get_db)) -> TeamMemberRead:
    """Update a team member's name and/or team."""
    tm = db.query(TeamMember).filter(TeamMember.id == team_member_id).first()
    if not tm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team member not found")

    if payload.name is not None:
        existing = db.query(TeamMember).filter(
            TeamMember.name == payload.name.strip(), TeamMember.id != team_member_id
        ).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Another team member has this name")
        tm.name = payload.name.strip()

    if payload.team_id is not None:
        t = db.query(Team).filter(Team.id == payload.team_id).first()
        if not t:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
        tm.team_id = payload.team_id

    db.commit()
    db.refresh(tm)
    return TeamMemberRead.model_validate(tm)


@router.delete("/team-members/{team_member_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_team_member(team_member_id: int, db: Session = Depends(get_db)):
    """Delete a team member."""
    tm = db.query(TeamMember).filter(TeamMember.id == team_member_id).first()
    if not tm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team member not found")
    db.delete(tm)
    db.commit()
