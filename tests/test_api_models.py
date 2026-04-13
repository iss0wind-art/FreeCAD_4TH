"""
Pydantic 모델 검증 테스트 (Phase 5)
"""

import pytest
from pydantic import ValidationError
from api.models import (
    MemberInputDTO, BOQCalculateRequest,
    BOQItemDTO, BOQCalculateResponse,
)


class TestMemberInputDTO:
    def test_valid_column(self):
        m = MemberInputDTO(
            member_id="C1",
            member_type="COLUMN",
            vertices_2d=[[-300, -300], [300, -300], [300, 300], [-300, 300]],
            height=3000.0,
        )
        assert m.member_id == "C1"
        assert m.z_base == 0.0

    def test_valid_beam(self):
        m = MemberInputDTO(
            member_id="B1",
            member_type="BEAM",
            vertices_2d=[[-1000, -150], [1000, -150], [1000, 150], [-1000, 150]],
            height=500.0,
        )
        assert m.member_type == "BEAM"

    def test_invalid_member_type(self):
        with pytest.raises(ValidationError):
            MemberInputDTO(
                member_id="X1", member_type="WALL",
                vertices_2d=[[-300,-300],[300,-300],[300,300]],
                height=3000.0,
            )

    def test_negative_height_rejected(self):
        with pytest.raises(ValidationError):
            MemberInputDTO(
                member_id="C1", member_type="COLUMN",
                vertices_2d=[[-300,-300],[300,-300],[300,300]],
                height=-100.0,
            )

    def test_zero_height_rejected(self):
        with pytest.raises(ValidationError):
            MemberInputDTO(
                member_id="C1", member_type="COLUMN",
                vertices_2d=[[-300,-300],[300,-300],[300,300]],
                height=0.0,
            )

    def test_excessive_height_rejected(self):
        with pytest.raises(ValidationError):
            MemberInputDTO(
                member_id="C1", member_type="COLUMN",
                vertices_2d=[[-300,-300],[300,-300],[300,300]],
                height=200_000.0,   # 200m 초과
            )

    def test_too_few_vertices_rejected(self):
        with pytest.raises(ValidationError):
            MemberInputDTO(
                member_id="C1", member_type="COLUMN",
                vertices_2d=[[-300,-300],[300,-300]],  # 2개만
                height=3000.0,
            )

    def test_invalid_vertex_shape(self):
        with pytest.raises(ValidationError):
            MemberInputDTO(
                member_id="C1", member_type="COLUMN",
                vertices_2d=[[-300,-300,0],[300,-300,0],[300,300,0]],  # 3D 좌표
                height=3000.0,
            )

    def test_empty_member_id_rejected(self):
        with pytest.raises(ValidationError):
            MemberInputDTO(
                member_id="", member_type="COLUMN",
                vertices_2d=[[-300,-300],[300,-300],[300,300]],
                height=3000.0,
            )


class TestBOQCalculateRequest:
    def test_valid_request(self):
        req = BOQCalculateRequest(
            project_id="PROJ-001",
            members=[
                MemberInputDTO(
                    member_id="C1", member_type="COLUMN",
                    vertices_2d=[[-300,-300],[300,-300],[300,300],[-300,300]],
                    height=3000.0,
                )
            ]
        )
        assert req.project_id == "PROJ-001"
        assert len(req.members) == 1

    def test_empty_members_rejected(self):
        with pytest.raises(ValidationError):
            BOQCalculateRequest(project_id="PROJ-001", members=[])

    def test_empty_project_id_rejected(self):
        with pytest.raises(ValidationError):
            BOQCalculateRequest(
                project_id="",
                members=[MemberInputDTO(
                    member_id="C1", member_type="COLUMN",
                    vertices_2d=[[-300,-300],[300,-300],[300,300]],
                    height=3000.0,
                )]
            )


class TestBOQItemDTO:
    def test_valid_item(self):
        item = BOQItemDTO(
            member_id="C1",
            volume_m3=1.08,
            formwork_area_m2=7.2,
            formwork_deduction_m2=0.6,
        )
        assert item.gltf_url is None

    def test_with_gltf_url(self):
        item = BOQItemDTO(
            member_id="C1",
            volume_m3=0.63,
            formwork_area_m2=6.6,
            formwork_deduction_m2=0.6,
            gltf_url="/output/gltf/C1.gltf",
        )
        assert item.gltf_url == "/output/gltf/C1.gltf"
