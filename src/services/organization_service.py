"""
Organization Master Service
Manages tenant-scoped organizational masters: Locations, Designations, Salary Templates, Components, and Shifts.
"""

import logging
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from src.database.models import (
    Tenant,
    Department,
    CompanyLocation,
    DesignationMaster,
    SalaryComponent,
    SalaryTemplate,
    EmployeeSalaryStructure,
    WorkShift,
    Student,
)

logger = logging.getLogger("organization_service")


class OrganizationService:
    def __init__(self, db: Session):
        self.db = db

    # =========================================================================
    # LOCATIONS
    # =========================================================================
    def list_locations(self, tenant_id: int) -> List[Dict[str, Any]]:
        locations = (
            self.db.query(CompanyLocation)
            .filter(CompanyLocation.tenant_id == tenant_id)
            .order_by(CompanyLocation.name.asc())
            .all()
        )
        return [loc.to_dict() for loc in locations]

    def get_location(self, tenant_id: int, location_id: int) -> Dict[str, Any]:
        loc = (
            self.db.query(CompanyLocation)
            .filter(CompanyLocation.id == location_id, CompanyLocation.tenant_id == tenant_id)
            .first()
        )
        if not loc:
            raise HTTPException(status_code=404, detail="Location not found.")
        return loc.to_dict()

    def create_location(self, tenant_id: int, payload: Any) -> Dict[str, Any]:
        code = (payload.code or payload.name[:4]).strip().upper()
        existing = (
            self.db.query(CompanyLocation)
            .filter(CompanyLocation.tenant_id == tenant_id, CompanyLocation.name == payload.name.strip())
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Location with name '{payload.name}' already exists in this institution.",
            )

        loc = CompanyLocation(
            tenant_id=tenant_id,
            name=payload.name.strip(),
            code=code,
            city=payload.city.strip() if payload.city else None,
            state=payload.state.strip() if payload.state else "Maharashtra",
            address=payload.address.strip() if payload.address else None,
            contact_number=payload.contact_number.strip() if payload.contact_number else None,
            is_active=payload.is_active if payload.is_active is not None else True,
        )
        self.db.add(loc)
        self.db.commit()
        self.db.refresh(loc)
        return loc.to_dict()

    def update_location(self, tenant_id: int, location_id: int, payload: Any) -> Dict[str, Any]:
        loc = (
            self.db.query(CompanyLocation)
            .filter(CompanyLocation.id == location_id, CompanyLocation.tenant_id == tenant_id)
            .first()
        )
        if not loc:
            raise HTTPException(status_code=404, detail="Location not found.")

        if payload.name is not None:
            loc.name = payload.name.strip()
        if payload.code is not None:
            loc.code = payload.code.strip().upper()
        if payload.city is not None:
            loc.city = payload.city.strip()
        if payload.state is not None:
            loc.state = payload.state.strip()
        if payload.address is not None:
            loc.address = payload.address.strip()
        if payload.contact_number is not None:
            loc.contact_number = payload.contact_number.strip()
        if payload.is_active is not None:
            loc.is_active = payload.is_active

        self.db.commit()
        self.db.refresh(loc)
        return loc.to_dict()

    def delete_location(self, tenant_id: int, location_id: int) -> Dict[str, Any]:
        loc = (
            self.db.query(CompanyLocation)
            .filter(CompanyLocation.id == location_id, CompanyLocation.tenant_id == tenant_id)
            .first()
        )
        if not loc:
            raise HTTPException(status_code=404, detail="Location not found.")

        assigned_employees = (
            self.db.query(Student)
            .filter(Student.tenant_id == tenant_id, Student.location_id == location_id)
            .count()
        )
        if assigned_employees > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot delete location '{loc.name}'. {assigned_employees} employee(s) are currently assigned here. Please reassign them first.",
            )

        self.db.delete(loc)
        self.db.commit()
        return {"status": "success", "message": f"Location '{loc.name}' deleted successfully."}

    # =========================================================================
    # DESIGNATIONS
    # =========================================================================
    def list_designations(self, tenant_id: int) -> List[Dict[str, Any]]:
        designations = (
            self.db.query(DesignationMaster)
            .filter(DesignationMaster.tenant_id == tenant_id)
            .order_by(DesignationMaster.title.asc())
            .all()
        )
        return [desig.to_dict() for desig in designations]

    def get_designation(self, tenant_id: int, designation_id: int) -> Dict[str, Any]:
        desig = (
            self.db.query(DesignationMaster)
            .filter(DesignationMaster.id == designation_id, DesignationMaster.tenant_id == tenant_id)
            .first()
        )
        if not desig:
            raise HTTPException(status_code=404, detail="Designation not found.")
        return desig.to_dict()

    def create_designation(self, tenant_id: int, payload: Any) -> Dict[str, Any]:
        code = (payload.code or payload.title[:4]).strip().upper()
        existing = (
            self.db.query(DesignationMaster)
            .filter(DesignationMaster.tenant_id == tenant_id, DesignationMaster.title == payload.title.strip())
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Designation '{payload.title}' already exists in this institution.",
            )

        desig = DesignationMaster(
            tenant_id=tenant_id,
            title=payload.title.strip(),
            code=code,
            department_id=payload.department_id,
            salary_template_id=payload.salary_template_id,
            description=payload.description.strip() if payload.description else None,
            is_active=payload.is_active if payload.is_active is not None else True,
        )
        self.db.add(desig)
        self.db.commit()
        self.db.refresh(desig)
        return desig.to_dict()

    def update_designation(self, tenant_id: int, designation_id: int, payload: Any) -> Dict[str, Any]:
        desig = (
            self.db.query(DesignationMaster)
            .filter(DesignationMaster.id == designation_id, DesignationMaster.tenant_id == tenant_id)
            .first()
        )
        if not desig:
            raise HTTPException(status_code=404, detail="Designation not found.")

        fields_set = getattr(payload, "model_fields_set", None) or getattr(payload, "__fields_set__", set())
        if payload.title is not None:
            desig.title = payload.title.strip()
        if payload.code is not None:
            desig.code = payload.code.strip().upper()
        if "department_id" in fields_set:
            desig.department_id = payload.department_id if (payload.department_id and payload.department_id > 0) else None
        if "salary_template_id" in fields_set:
            if payload.salary_template_id and payload.salary_template_id > 0:
                tpl = self.db.query(SalaryTemplate).filter(SalaryTemplate.id == payload.salary_template_id, SalaryTemplate.tenant_id == tenant_id).first()
                desig.salary_template_id = tpl.id if tpl else None
            else:
                desig.salary_template_id = None
        if payload.description is not None:
            desig.description = payload.description.strip()
        if payload.is_active is not None:
            desig.is_active = payload.is_active

        self.db.commit()
        self.db.refresh(desig)
        return desig.to_dict()

    def delete_designation(self, tenant_id: int, designation_id: int) -> Dict[str, Any]:
        desig = (
            self.db.query(DesignationMaster)
            .filter(DesignationMaster.id == designation_id, DesignationMaster.tenant_id == tenant_id)
            .first()
        )
        if not desig:
            raise HTTPException(status_code=404, detail="Designation not found.")

        assigned_employees = (
            self.db.query(Student)
            .filter(
                Student.tenant_id == tenant_id,
                Student.designation_id == designation_id,
                Student.is_active == True,
            )
            .count()
        )
        if assigned_employees > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot delete designation '{desig.title}' because {assigned_employees} employee(s) are currently assigned to it. Please reassign them first.",
            )

        self.db.delete(desig)
        self.db.commit()
        return {"status": "success", "message": f"Designation '{desig.title}' deleted successfully."}

    # =========================================================================
    # SALARY COMPONENTS
    # =========================================================================
    def list_salary_components(self, tenant_id: int) -> List[Dict[str, Any]]:
        components = (
            self.db.query(SalaryComponent)
            .filter(SalaryComponent.tenant_id == tenant_id)
            .order_by(SalaryComponent.name.asc())
            .all()
        )
        return [c.to_dict() for c in components]

    def get_salary_component(self, tenant_id: int, component_id: int) -> Dict[str, Any]:
        comp = (
            self.db.query(SalaryComponent)
            .filter(SalaryComponent.id == component_id, SalaryComponent.tenant_id == tenant_id)
            .first()
        )
        if not comp:
            raise HTTPException(status_code=404, detail="Salary Component not found.")
        return comp.to_dict()

    def create_salary_component(self, tenant_id: int, payload: Any) -> Dict[str, Any]:
        code = payload.code.strip().upper()
        existing = (
            self.db.query(SalaryComponent)
            .filter(SalaryComponent.tenant_id == tenant_id, SalaryComponent.code == code)
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Salary Component with code '{code}' already exists.",
            )

        comp = SalaryComponent(
            tenant_id=tenant_id,
            name=payload.name.strip(),
            code=code,
            component_type=payload.component_type,
            calculation_type=payload.calculation_type,
            default_value=payload.default_value,
            is_taxable=payload.is_taxable,
            is_statutory=payload.is_statutory,
            is_active=payload.is_active,
        )
        self.db.add(comp)
        self.db.commit()
        self.db.refresh(comp)
        return comp.to_dict()

    def update_salary_component(self, tenant_id: int, component_id: int, payload: Any) -> Dict[str, Any]:
        comp = (
            self.db.query(SalaryComponent)
            .filter(SalaryComponent.id == component_id, SalaryComponent.tenant_id == tenant_id)
            .first()
        )
        if not comp:
            raise HTTPException(status_code=404, detail="Salary Component not found.")

        if payload.name is not None:
            comp.name = payload.name.strip()
        if payload.component_type is not None:
            comp.component_type = payload.component_type
        if payload.calculation_type is not None:
            comp.calculation_type = payload.calculation_type
        if payload.default_value is not None:
            comp.default_value = payload.default_value
        if payload.is_taxable is not None:
            comp.is_taxable = payload.is_taxable
        if payload.is_statutory is not None:
            comp.is_statutory = payload.is_statutory
        if payload.is_active is not None:
            comp.is_active = payload.is_active

        self.db.commit()
        self.db.refresh(comp)
        return comp.to_dict()

    def delete_salary_component(self, tenant_id: int, component_id: int) -> Dict[str, Any]:
        comp = (
            self.db.query(SalaryComponent)
            .filter(SalaryComponent.id == component_id, SalaryComponent.tenant_id == tenant_id)
            .first()
        )
        if not comp:
            raise HTTPException(status_code=404, detail="Salary Component not found.")

        self.db.delete(comp)
        self.db.commit()
        return {"status": "success", "message": f"Component '{comp.name}' deleted successfully."}

    # =========================================================================
    # SALARY TEMPLATES
    # =========================================================================
    def list_salary_templates(self, tenant_id: int) -> List[Dict[str, Any]]:
        templates = (
            self.db.query(SalaryTemplate)
            .filter(SalaryTemplate.tenant_id == tenant_id)
            .order_by(SalaryTemplate.name.asc())
            .all()
        )
        return [tpl.to_dict() for tpl in templates]

    def get_salary_template(self, tenant_id: int, template_id: int) -> Dict[str, Any]:
        tpl = (
            self.db.query(SalaryTemplate)
            .filter(SalaryTemplate.id == template_id, SalaryTemplate.tenant_id == tenant_id)
            .first()
        )
        if not tpl:
            raise HTTPException(status_code=404, detail="Salary Template not found.")
        return tpl.to_dict()

    def create_salary_template(self, tenant_id: int, payload: Any) -> Dict[str, Any]:
        code = payload.code.strip().upper()
        existing = (
            self.db.query(SalaryTemplate)
            .filter(SalaryTemplate.tenant_id == tenant_id, SalaryTemplate.code == code)
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Salary Template with code '{code}' already exists.",
            )

        tpl = SalaryTemplate(
            tenant_id=tenant_id,
            name=payload.name.strip(),
            code=code,
            compensation_model=payload.compensation_model,
            description=payload.description.strip() if payload.description else None,
            basic_percentage=payload.basic_percentage,
            hra_percentage=payload.hra_percentage,
            da_percentage=payload.da_percentage,
            conveyance_fixed=payload.conveyance_fixed,
            medical_fixed=payload.medical_fixed,
            enable_pf=payload.enable_pf,
            pf_capped_at_ceiling=payload.pf_capped_at_ceiling,
            enable_esi=payload.enable_esi,
            enable_pt=payload.enable_pt,
            is_active=payload.is_active,
        )
        self.db.add(tpl)
        self.db.commit()
        self.db.refresh(tpl)
        return tpl.to_dict()

    def update_salary_template(self, tenant_id: int, template_id: int, payload: Any) -> Dict[str, Any]:
        tpl = (
            self.db.query(SalaryTemplate)
            .filter(SalaryTemplate.id == template_id, SalaryTemplate.tenant_id == tenant_id)
            .first()
        )
        if not tpl:
            raise HTTPException(status_code=404, detail="Salary Template not found.")

        if payload.name is not None:
            tpl.name = payload.name.strip()
        if payload.compensation_model is not None:
            tpl.compensation_model = payload.compensation_model
        if payload.description is not None:
            tpl.description = payload.description.strip()
        if payload.basic_percentage is not None:
            tpl.basic_percentage = payload.basic_percentage
        if payload.hra_percentage is not None:
            tpl.hra_percentage = payload.hra_percentage
        if payload.da_percentage is not None:
            tpl.da_percentage = payload.da_percentage
        if payload.conveyance_fixed is not None:
            tpl.conveyance_fixed = payload.conveyance_fixed
        if payload.medical_fixed is not None:
            tpl.medical_fixed = payload.medical_fixed
        if payload.enable_pf is not None:
            tpl.enable_pf = payload.enable_pf
        if payload.pf_capped_at_ceiling is not None:
            tpl.pf_capped_at_ceiling = payload.pf_capped_at_ceiling
        if payload.enable_esi is not None:
            tpl.enable_esi = payload.enable_esi
        if payload.enable_pt is not None:
            tpl.enable_pt = payload.enable_pt
        if payload.is_active is not None:
            tpl.is_active = payload.is_active

        self.db.commit()
        self.db.refresh(tpl)
        return tpl.to_dict()

    def delete_salary_template(self, tenant_id: int, template_id: int) -> Dict[str, Any]:
        tpl = (
            self.db.query(SalaryTemplate)
            .filter(SalaryTemplate.id == template_id, SalaryTemplate.tenant_id == tenant_id)
            .first()
        )
        if not tpl:
            raise HTTPException(status_code=404, detail="Salary Template not found.")

        assigned_structures = (
            self.db.query(EmployeeSalaryStructure)
            .filter(EmployeeSalaryStructure.tenant_id == tenant_id, EmployeeSalaryStructure.template_id == template_id)
            .count()
        )
        if assigned_structures > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot delete template '{tpl.name}'. {assigned_structures} salary structure(s) are actively using it.",
            )

        assigned_designations = (
            self.db.query(DesignationMaster)
            .filter(DesignationMaster.tenant_id == tenant_id, DesignationMaster.salary_template_id == template_id)
            .count()
        )
        if assigned_designations > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot delete template '{tpl.name}'. {assigned_designations} designation(s) are actively bound to this template.",
            )

        self.db.delete(tpl)
        self.db.commit()
        return {"status": "success", "message": f"Template '{tpl.name}' deleted successfully."}
