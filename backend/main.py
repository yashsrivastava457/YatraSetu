from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import engine, Base, get_db
from models import users, zone, crowddata, Alert, temples
from risk_engine import calculate_risk
import os
import requests


app = FastAPI(
    title="YatraSetu",
    description="Safe Secure Smart",
    version="1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_headers=["*"],
    allow_methods=["*"]
)


@app.get("/")
def root():
    return "YatraSetu is running"


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/api/db-test")
def db_test():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {"database": "connected"}

    except Exception as e:
        return {
            "database": "connection failed",
            "error": str(e)
        }


# ---------------------------------------------------------
# AUTHORIZATION
# ---------------------------------------------------------

def get_current_user(authorization: str = Header(None), db: Session = Depends(get_db)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization token required")

    token = authorization[7:].strip()
    supabase_url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_key:
        raise HTTPException(status_code=500, detail="Supabase server configuration missing")

    try:
        r = requests.get(
            f"{supabase_url}/auth/v1/user",
            headers={"apikey": service_key, "Authorization": f"Bearer {token}"},
            timeout=10
        )
    except Exception:
        raise HTTPException(status_code=500, detail="Unable to verify Supabase user")

    if r.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid or expired login session")

    auth_id = r.json().get("id")
    current = db.query(users).filter(users.auth_user_id == auth_id).first()
    if not current:
        raise HTTPException(status_code=403, detail="YatraSetu user profile not found")
    return current


def require_super_admin(current_user = Depends(get_current_user)):
    if current_user.roles != "SUPER_ADMIN":
        raise HTTPException(status_code=403, detail="Only Super Admin can perform this action")
    return current_user


def require_temple_access(temple_id: int, current_user = Depends(get_current_user)):
    if current_user.roles == "SUPER_ADMIN":
        return current_user
    if current_user.roles == "TEMPLE_ADMIN" and current_user.temple_id == temple_id:
        return current_user
    raise HTTPException(status_code=403, detail="You do not have access to this temple")


def require_zone_access(zone_id: int, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    z = db.query(zone).filter(zone.id == zone_id).first()
    if not z:
        raise HTTPException(status_code=404, detail="Zone not found")
    if current_user.roles == "SUPER_ADMIN" or (current_user.roles == "TEMPLE_ADMIN" and current_user.temple_id == z.temple_id):
        return current_user
    raise HTTPException(status_code=403, detail="You do not have access to this zone")


# ---------------------------------------------------------
# TEMPLES
# ---------------------------------------------------------

@app.post("/api/temples")
def create_temple(
    name: str,
    location: str,
    description: str = "",
    opening_time: str = "",
    closing_time: str = "",
    contact: str = "",
    db: Session = Depends(get_db),
    current_user = Depends(require_super_admin)
):
    temple = temples(
        name=name,
        location=location,
        description=description,
        opening_time=opening_time,
        closing_time=closing_time,
        contact=contact
    )

    db.add(temple)
    db.commit()
    db.refresh(temple)

    return {
        "message": "Temple created successfully",
        "temple_id": temple.id,
        "name": temple.name,
        "location": temple.location
    }


@app.get("/api/temples")
def get_temples(
    db: Session = Depends(get_db),
    current_user = Depends(require_super_admin)
):
    return db.query(temples).order_by(temples.id.asc()).all()


@app.get("/api/temples/{temple_id}")
def get_temple(
    temple_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_temple_access)
):
    temple = (
        db.query(temples)
        .filter(temples.id == temple_id)
        .first()
    )

    if not temple:
        raise HTTPException(
            status_code=404,
            detail="Temple not found"
        )

    return {
        "id": temple.id,
        "name": temple.name,
        "location": temple.location,
        "description": temple.description,
        "opening_time": temple.opening_time,
        "closing_time": temple.closing_time,
        "contact": temple.contact
    }


# ---------------------------------------------------------
# TEMPLE-SPECIFIC ZONES
# IMPORTANT: every zone belongs to exactly one temple.
# ---------------------------------------------------------

@app.post("/api/temples/{temple_id}/zones")
def create_temple_zone(
    temple_id: int,
    name: str,
    type: str = "OTHER",
    capacity: int = 0,
    db: Session = Depends(get_db),
    current_user = Depends(require_temple_access)
):
    temple = (
        db.query(temples)
        .filter(temples.id == temple_id)
        .first()
    )

    if not temple:
        raise HTTPException(
            status_code=404,
            detail="Temple not found"
        )

    name = name.strip()

    if not name:
        raise HTTPException(
            status_code=400,
            detail="Zone name is required"
        )

    if capacity < 1:
        raise HTTPException(
            status_code=400,
            detail="Capacity must be greater than 0"
        )

    allowed_types = {
        "ENTRANCE",
        "QUEUE",
        "DARSHAN",
        "PARKING",
        "EXIT",
        "OTHER"
    }

    type = type.upper()

    if type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="Invalid zone type"
        )

    # Prevent duplicate zone names inside the SAME temple.
    # The same name can still be used by another temple.
    existing = (
        db.query(zone)
        .filter(
            zone.temple_id == temple_id,
            zone.name.ilike(name)
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail="A zone with this name already exists in this temple"
        )

    new_zone = zone(
        temple_id=temple_id,
        name=name,
        types=type,
        capacity=capacity
    )

    db.add(new_zone)
    db.commit()
    db.refresh(new_zone)

    return {
        "message": "Zone created successfully",
        "zone_id": new_zone.id,
        "temple_id": temple_id,
        "zone_name": new_zone.name,
        "type": new_zone.types,
        "capacity": new_zone.capacity,
        "crowd_count": new_zone.crowd_count,
        "risk": new_zone.risk
    }


@app.get("/api/temples/{temple_id}/zones")
def get_temple_zones(
    temple_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_temple_access)
):
    temple = (
        db.query(temples)
        .filter(temples.id == temple_id)
        .first()
    )

    if not temple:
        raise HTTPException(
            status_code=404,
            detail="Temple not found"
        )

    zones = (
        db.query(zone)
        .filter(zone.temple_id == temple_id)
        .order_by(zone.id.asc())
        .all()
    )

    # Return a clean API shape. Frontend receives `type`,
    # while the database keeps its existing `types` column.
    return [
        {
            "id": z.id,
            "temple_id": z.temple_id,
            "name": z.name,
            "type": z.types,
            "capacity": z.capacity,
            "crowd_count": z.crowd_count,
            "risk": z.risk or "LOW"
        }
        for z in zones
    ]


# ---------------------------------------------------------
# CROWD
# ---------------------------------------------------------

@app.post("/api/crowd/update")
def update_crowd(
    zone_id: int,
    people_count: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_zone_access)
):
    if people_count < 0:
        raise HTTPException(
            status_code=400,
            detail="People count cannot be negative"
        )

    z = (
        db.query(zone)
        .filter(zone.id == zone_id)
        .first()
    )

    if not z:
        raise HTTPException(
            status_code=404,
            detail="Zone not found"
        )

    result = calculate_risk(
        people_count,
        z.capacity
    )

    z.crowd_count = people_count
    z.risk = result["risk"]

    crowd = crowddata(
        zone_id=z.id,
        people_count=people_count,
        density=result["Occupancy"]
    )

    db.add(crowd)
    db.commit()
    db.refresh(crowd)

    return {
        "message": "Database updated successfully",
        "temple_id": z.temple_id,
        "zone_id": z.id,
        "zone": z.name,
        "people_count": people_count,
        "capacity": z.capacity,
        "occupancy": result["Occupancy"],
        "risk": result["risk"]
    }


@app.get("/api/crowd/{zone_id}")
def get_crowd(
    zone_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_zone_access)
):
    z = (
        db.query(zone)
        .filter(zone.id == zone_id)
        .first()
    )

    if not z:
        raise HTTPException(
            status_code=404,
            detail="Zone not found"
        )

    c = (
        db.query(crowddata)
        .filter(crowddata.zone_id == zone_id)
        .order_by(crowddata.timestamp.desc())
        .first()
    )

    return {
        "temple_id": z.temple_id,
        "zone_id": z.id,
        "zone_name": z.name,
        "capacity": z.capacity,
        "current_crowd": z.crowd_count,
        "density": c.density if c else 0,
        "risk": z.risk or "LOW"
    }

@app.post("/api/admin/create-temple")
def create_temple_with_admin(
    name: str,
    location: str,
    description: str = "",
    opening_time: str = "",
    closing_time: str = "",
    contact: str = "",
    admin_name: str = "",
    admin_email: str = "",
    admin_password: str = "",
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):

    # -----------------------------------
    # Check Authorization
    # -----------------------------------

    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Authorization token required"
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header"
        )

    access_token = authorization.replace(
        "Bearer ",
        "",
        1
    )


    # -----------------------------------
    # Supabase settings
    # -----------------------------------

    supabase_url = os.getenv(
        "SUPABASE_URL"
    )

    service_key = os.getenv(
        "SUPABASE_SERVICE_ROLE_KEY"
    )


    if not supabase_url or not service_key:

        raise HTTPException(
            status_code=500,
            detail="Supabase server configuration missing"
        )


    # -----------------------------------
    # Verify logged-in Supabase user
    # -----------------------------------

    try:

        user_response = requests.get(

            f"{supabase_url}/auth/v1/user",

            headers={
                "apikey": service_key,
                "Authorization":
                    f"Bearer {access_token}"
            },

            timeout=10
        )

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail="Unable to verify Supabase user"
        )


    if user_response.status_code != 200:

        raise HTTPException(
            status_code=401,
            detail="Invalid or expired login session"
        )


    auth_user = user_response.json()

    auth_user_id = auth_user.get("id")


    # -----------------------------------
    # Verify SUPER ADMIN
    # -----------------------------------

    current_admin = (
        db.query(users)
        .filter(
            users.auth_user_id == auth_user_id
        )
        .first()
    )


    if not current_admin:

        raise HTTPException(
            status_code=403,
            detail="YatraSetu user profile not found"
        )


    if current_admin.roles != "SUPER_ADMIN":

        raise HTTPException(
            status_code=403,
            detail="Only Super Admin can create temples"
        )


    # -----------------------------------
    # Validate input
    # -----------------------------------

    if not name.strip():

        raise HTTPException(
            status_code=400,
            detail="Temple name is required"
        )


    if not location.strip():

        raise HTTPException(
            status_code=400,
            detail="Temple location is required"
        )


    if not admin_name.strip():

        raise HTTPException(
            status_code=400,
            detail="Admin name is required"
        )


    if not admin_email.strip():

        raise HTTPException(
            status_code=400,
            detail="Admin email is required"
        )


    if len(admin_password) < 6:

        raise HTTPException(
            status_code=400,
            detail="Admin password must be at least 6 characters"
        )

    existing_profile = (
        db.query(users)
        .filter(users.email == admin_email.strip())
        .first()
    )

    if existing_profile:
        raise HTTPException(
            status_code=409,
            detail="A YatraSetu user with this email already exists"
        )


    # -----------------------------------
    # Create Temple
    # -----------------------------------

    try:

        new_temple = temples(

            name=name.strip(),

            location=location.strip(),

            description=(
                description.strip()
                if description
                else None
            ),

            opening_time=opening_time.strip(),

            closing_time=closing_time.strip(),

            contact=contact.strip()

        )

        db.add(new_temple)

        db.commit()

        db.refresh(new_temple)


        temple_id = new_temple.id


    except Exception as e:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Failed to create temple: {str(e)}"
        )


    # -----------------------------------
    # Create Supabase Auth User
    # -----------------------------------

    try:

        auth_response = requests.post(

            f"{supabase_url}/auth/v1/admin/users",

            headers={
                "apikey": service_key,
                "Authorization":
                    f"Bearer {service_key}",
                "Content-Type":
                    "application/json"
            },

            json={
                "email": admin_email.strip(),
                "password": admin_password,
                "email_confirm": True
            },

            timeout=10
        )


        if auth_response.status_code not in [200, 201]:

            db.delete(new_temple)
            db.commit()

            try:

                error_data = auth_response.json()

                error_message = (
                    error_data.get("message")
                    or error_data.get("msg")
                    or "Failed to create Auth user"
                )

            except Exception:

                error_message = (
                    "Failed to create Auth user"
                )


            raise HTTPException(
                status_code=400,
                detail=error_message
            )


        new_auth_user = auth_response.json()

        new_auth_user_id = new_auth_user.get("id")


    except HTTPException:

        raise

    except Exception as e:

        db.delete(new_temple)
        db.commit()

        raise HTTPException(
            status_code=500,
            detail="Failed to create Temple Admin account"
        )


    # -----------------------------------
    # Create YatraSetu public.users record
    # -----------------------------------

    try:

        new_admin = users(

            name=admin_name.strip(),

            email=admin_email.strip(),

            password_hash=None,

            roles="TEMPLE_ADMIN",

            temple_id=temple_id,

            auth_user_id=new_auth_user_id

        )

        db.add(new_admin)

        db.commit()

        db.refresh(new_admin)


    except Exception as e:

        db.rollback()

        # Remove Auth user if profile creation fails

        try:

            requests.delete(

                f"{supabase_url}/auth/v1/admin/users/{new_auth_user_id}",

                headers={
                    "apikey": service_key,
                    "Authorization":
                        f"Bearer {service_key}"
                },

                timeout=10
            )

        except Exception:

            pass


        try:

            db.delete(new_temple)
            db.commit()

        except Exception:

            db.rollback()


        raise HTTPException(
            status_code=500,
            detail="Temple Admin profile creation failed"
        )


    # -----------------------------------
    # Success
    # -----------------------------------

    return {

        "message":
            "Temple and Temple Admin created successfully",

        "temple_id":
            temple_id,

        "temple_name":
            new_temple.name,

        "admin_id":
            new_admin.id,

        "admin_name":
            new_admin.name,

        "admin_email":
            new_admin.email,

        "role":
            new_admin.roles

    }
Base.metadata.create_all(bind=engine)

@app.post("/api/admin/create-temple-admin")
def create_temple_admin(
    temple_id: int,
    admin_name: str,
    admin_email: str,
    admin_password: str,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization token required")

    access_token = authorization.replace("Bearer ", "", 1)
    supabase_url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_key:
        raise HTTPException(status_code=500, detail="Supabase server configuration missing")

    try:
        user_response = requests.get(
            f"{supabase_url}/auth/v1/user",
            headers={"apikey": service_key, "Authorization": f"Bearer {access_token}"},
            timeout=10
        )
    except Exception:
        raise HTTPException(status_code=500, detail="Unable to verify Supabase user")

    if user_response.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid or expired login session")

    auth_user_id = user_response.json().get("id")
    current_admin = db.query(users).filter(users.auth_user_id == auth_user_id).first()
    if not current_admin or current_admin.roles != "SUPER_ADMIN":
        raise HTTPException(status_code=403, detail="Only Super Admin can create Temple Admins")

    temple = db.query(temples).filter(temples.id == temple_id).first()
    if not temple:
        raise HTTPException(status_code=404, detail="Temple not found")

    if not admin_name.strip() or not admin_email.strip():
        raise HTTPException(status_code=400, detail="Admin name and email are required")
    if len(admin_password) < 6:
        raise HTTPException(status_code=400, detail="Admin password must be at least 6 characters")

    existing = db.query(users).filter(users.email == admin_email.strip()).first()
    if existing:
        raise HTTPException(status_code=409, detail="A YatraSetu user with this email already exists")

    auth_response = requests.post(
        f"{supabase_url}/auth/v1/admin/users",
        headers={"apikey": service_key, "Authorization": f"Bearer {service_key}", "Content-Type": "application/json"},
        json={"email": admin_email.strip(), "password": admin_password, "email_confirm": True},
        timeout=10
    )
    if auth_response.status_code not in [200, 201]:
        try:
            detail = auth_response.json().get("message") or auth_response.json().get("msg") or "Failed to create Auth user"
        except Exception:
            detail = "Failed to create Auth user"
        raise HTTPException(status_code=400, detail=detail)

    new_auth_user_id = auth_response.json().get("id")
    try:
        new_admin = users(
            name=admin_name.strip(), email=admin_email.strip(), password_hash=None,
            roles="TEMPLE_ADMIN", temple_id=temple_id, auth_user_id=new_auth_user_id
        )
        db.add(new_admin)
        db.commit()
        db.refresh(new_admin)
    except Exception:
        db.rollback()
        try:
            requests.delete(
                f"{supabase_url}/auth/v1/admin/users/{new_auth_user_id}",
                headers={"apikey": service_key, "Authorization": f"Bearer {service_key}"},
                timeout=10
            )
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Temple Admin profile creation failed")

    return {
        "message": "Temple Admin created successfully",
        "temple_id": temple_id,
        "temple_name": temple.name,
        "admin_id": new_admin.id,
        "admin_name": new_admin.name,
        "admin_email": new_admin.email,
        "role": new_admin.roles
    }


# ---------------------------------------------------------
# SUPER ADMIN: RESET TEMPLE CROWD DATA
# ---------------------------------------------------------

@app.post("/api/admin/temples/{temple_id}/reset-crowd")
def reset_temple_crowd(
    temple_id: int,
    current_user=Depends(require_super_admin),
    db: Session = Depends(get_db)
):
    temple = db.query(temples).filter(temples.id == temple_id).first()
    if not temple:
        raise HTTPException(status_code=404, detail="Temple not found")

    zone_ids = [
        z.id for z in
        db.query(zone.id).filter(zone.temple_id == temple_id).all()
    ]

    deleted = 0
    if zone_ids:
        deleted = db.query(crowddata).filter(
            crowddata.zone_id.in_(zone_ids)
        ).delete(synchronize_session=False)

        db.query(zone).filter(
            zone.id.in_(zone_ids)
        ).update(
            {"crowd_count": 0, "risk": "LOW"},
            synchronize_session=False
        )

    db.commit()

    return {
        "message": "All crowd data for this temple has been reset",
        "temple_id": temple_id,
        "deleted_records": deleted
    }


# ---------------------------------------------------------
# SUPER ADMIN MANAGEMENT / CRUD
# ---------------------------------------------------------

@app.put("/api/admin/temples/{temple_id}")
def admin_update_temple(
    temple_id: int,
    name: str = "",
    location: str = "",
    description: str = "",
    opening_time: str = "",
    closing_time: str = "",
    contact: str = "",
    current_user=Depends(require_super_admin),
    db: Session = Depends(get_db)
):
    temple = db.query(temples).filter(temples.id == temple_id).first()
    if not temple:
        raise HTTPException(status_code=404, detail="Temple not found")
    if name.strip(): temple.name = name.strip()
    if location.strip(): temple.location = location.strip()
    temple.description = description.strip()
    temple.opening_time = opening_time
    temple.closing_time = closing_time
    temple.contact = contact
    db.commit()
    db.refresh(temple)
    return {"message": "Temple updated successfully", "temple_id": temple.id}


@app.delete("/api/admin/temples/{temple_id}")
def admin_delete_temple(
    temple_id: int,
    current_user=Depends(require_super_admin),
    db: Session = Depends(get_db)
):
    temple = db.query(temples).filter(temples.id == temple_id).first()
    if not temple:
        raise HTTPException(status_code=404, detail="Temple not found")

    admins = db.query(users).filter(
        users.temple_id == temple_id,
        users.roles == "TEMPLE_ADMIN"
    ).all()
    auth_ids = [u.auth_user_id for u in admins if u.auth_user_id]

    zone_ids = [z.id for z in db.query(zone).filter(zone.temple_id == temple_id).all()]
    if zone_ids:
        db.query(crowddata).filter(crowddata.zone_id.in_(zone_ids)).delete(synchronize_session=False)
        db.query(Alert).filter(Alert.zone_id.in_(zone_ids)).delete(synchronize_session=False)
        db.query(zone).filter(zone.id.in_(zone_ids)).delete(synchronize_session=False)

    db.query(users).filter(users.temple_id == temple_id).delete(synchronize_session=False)
    db.delete(temple)
    db.commit()

    supabase_url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if supabase_url and service_key:
        for auth_id in auth_ids:
            try:
                requests.delete(
                    f"{supabase_url}/auth/v1/admin/users/{auth_id}",
                    headers={"apikey": service_key, "Authorization": f"Bearer {service_key}"},
                    timeout=10
                )
            except Exception:
                pass

    return {"message": "Temple and associated data deleted successfully", "temple_id": temple_id}


@app.put("/api/admin/zones/{zone_id}")
def admin_update_zone(
    zone_id: int,
    name: str,
    type: str = "OTHER",
    capacity: int = 1,
    crowd_count: int = 0,
    current_user=Depends(require_super_admin),
    db: Session = Depends(get_db)
):
    z = db.query(zone).filter(zone.id == zone_id).first()
    if not z:
        raise HTTPException(status_code=404, detail="Zone not found")
    name = name.strip()
    type = type.upper()
    if not name: raise HTTPException(status_code=400, detail="Zone name is required")
    if capacity < 1: raise HTTPException(status_code=400, detail="Capacity must be greater than 0")
    if crowd_count < 0: raise HTTPException(status_code=400, detail="Crowd count cannot be negative")
    if type not in {"ENTRANCE","QUEUE","DARSHAN","PARKING","EXIT","OTHER"}:
        raise HTTPException(status_code=400, detail="Invalid zone type")
    duplicate = db.query(zone).filter(
        zone.temple_id == z.temple_id, zone.id != z.id, zone.name.ilike(name)
    ).first()
    if duplicate:
        raise HTTPException(status_code=409, detail="A zone with this name already exists in this temple")
    result = calculate_risk(crowd_count, capacity)
    z.name, z.types, z.capacity, z.crowd_count, z.risk = name, type, capacity, crowd_count, result["risk"]
    db.commit()
    db.refresh(z)
    return {"message":"Zone updated successfully","zone_id":z.id,"temple_id":z.temple_id,
            "name":z.name,"type":z.types,"capacity":z.capacity,"crowd_count":z.crowd_count,
            "risk":z.risk,"occupancy":result["Occupancy"]}


@app.delete("/api/admin/zones/{zone_id}")
def admin_delete_zone(
    zone_id: int,
    current_user=Depends(require_super_admin),
    db: Session = Depends(get_db)
):
    z = db.query(zone).filter(zone.id == zone_id).first()
    if not z: raise HTTPException(status_code=404, detail="Zone not found")
    db.query(crowddata).filter(crowddata.zone_id == zone_id).delete(synchronize_session=False)
    db.query(Alert).filter(Alert.zone_id == zone_id).delete(synchronize_session=False)
    temple_id = z.temple_id
    db.delete(z)
    db.commit()
    return {"message":"Zone and crowd history deleted successfully","zone_id":zone_id,"temple_id":temple_id}
