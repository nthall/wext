import pytest

from dear_petition.petition.etl.load import link_offense_records_and_attachments
from dear_petition.petition.etl.paginator import OffenseRecordPaginator
from dear_petition.petition.types import dismissed
from dear_petition.petition import constants
from dear_petition.petition.tests.factories import (
    CIPRSRecordFactory,
    OffenseFactory,
    OffenseRecordFactory,
)

pytestmark = pytest.mark.django_db


def many_offense_records(batch, size):
    for i in range(size):
        record = CIPRSRecordFactory(
            batch=batch, jurisdiction=constants.DISTRICT_COURT, county="DURHAM"
        )
        offense = OffenseFactory(
            disposition_method=dismissed.DISMISSED_DISPOSITION_METHODS[0],
            ciprs_record=record,
            jurisdiction=constants.DISTRICT_COURT,
        )
        OffenseRecordFactory(offense=offense, action="CHARGED")


@pytest.fixture
def records_10(batch):
    return many_offense_records(batch=batch, size=10)


@pytest.fixture
def records_11(batch):
    return many_offense_records(batch=batch, size=11)


@pytest.fixture
def records_35(batch):
    return many_offense_records(batch=batch, size=35)


@pytest.fixture
def paginator(petition):
    return petition.get_offense_record_paginator()


@pytest.mark.parametrize("initial_page_size,expected", [[10, 10], [0, 10], [-10, 10]])
def test_paginator_initial_page_size(petition, initial_page_size, expected):
    paginator = OffenseRecordPaginator(petition, initial_page_size=initial_page_size)
    assert paginator.initial_page_size == expected


@pytest.mark.parametrize(
    "attachment_page_size,expected", [[10, 10], [0, 20], [-10, 20]]
)
def test_paginator_attachment_page_size(petition, attachment_page_size, expected):
    paginator = OffenseRecordPaginator(
        petition, attachment_page_size=attachment_page_size
    )
    assert paginator.attachment_page_size == expected


def test_paginator_petition_offense_records(paginator, records_11):
    assert paginator.petition_offense_records().count() == 10


def test_paginator_attachment_records__10(paginator, records_10):
    # no attachments
    assert not list(paginator.attachment_offense_records())


def test_paginator_attachment_records__11(paginator, records_11):
    records = list(paginator.attachment_offense_records())
    # one attachment
    assert len(records) == 1
    # first attachment has 1 record
    assert records[0].count() == 1


def test_paginator_attachment_records__25(paginator, records_35):
    records = list(paginator.attachment_offense_records())
    # two attachments
    assert len(records) == 2
    # first attachment has 20 records
    assert records[0].count() == 20
    # 2nd attachment has 5 records
    assert records[1].count() == 5


def test_link_offense_records__10(petition, records_10):
    link_offense_records_and_attachments(petition)
    assert petition.offense_records.count() == 10
    assert not petition.attachments.exists()


def test_link_offense_records__11(petition, records_11):
    link_offense_records_and_attachments(petition)
    # one attachment
    assert petition.attachments.count() == 1
    # first attachment has 1 record
    assert petition.attachments.first().offense_records.count() == 1


def test_link_offense_records__25(petition, records_35):
    link_offense_records_and_attachments(petition)
    # two attachments
    assert petition.attachments.count() == 2
    attachments = petition.attachments.order_by("pk")
    # first attachment has 20 records
    assert attachments[0].offense_records.count() == 20
    # 2nd attachment has 5 records
    assert attachments[1].offense_records.count() == 5


def test_paginator_same_record_number_order(petition, records_10):
    # get the 10th offense record so we can attach one more offense
    # record to the same CIPRSRecord, so that it crosses the
    # attachment boundary
    charge_1 = petition.get_all_offense_records().last()
    # attach a 2nd dismissed charge
    charge_2 = OffenseRecordFactory(
        offense=OffenseFactory(
            disposition_method=dismissed.DISMISSED_DISPOSITION_METHODS[0],
            ciprs_record=charge_1.offense.ciprs_record,
            jurisdiction=constants.DISTRICT_COURT,
        ),
        action="CHARGED",
    )
    link_offense_records_and_attachments(petition)
    attachment = petition.attachments.order_by("pk").first()
    # the 1st charge should always be on the first petition
    assert charge_1.pk in petition.offense_records.values_list("pk", flat=True)
    # the 2nd charge should always be on the attachment
    assert charge_2.pk in attachment.offense_records.values_list("pk", flat=True)
