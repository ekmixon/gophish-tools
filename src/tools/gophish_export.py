"""Export all the data from an assessment within GoPhish into a single JSON file.

Usage:
  gophish-export [--log-level=LEVEL] ASSESSMENT_ID SERVER API_KEY
  gophish-export (-h | --help)
  gophish-export --version

Options:
  API_KEY                   GoPhish API key.
  ASSESSMENT_ID             ID of the assessment to export data from.
  SERVER                    Full URL to GoPhish server.
  -h --help                 Show this screen.
  --version                 Show version.
  -l --log-level=LEVEL      If specified, then the log level will be set to
                            the specified value.  Valid values are "debug", "info",
                            "warning", "error", and "critical". [default: info]
"""

# Standard Python Libraries
from datetime import datetime
import hashlib
import json
import logging
import re
import sys
from typing import Dict

# Third-Party Libraries
from docopt import docopt
import httpagentparser
import requests

# cisagov Libraries
from tools.connect import connect_api

from ._version import __version__

# Disable "Insecure Request" warning: GoPhish uses a self-signed certificate
# as default for https connections, which can not be  verified by a third
# party; thus, an SSL insecure request warning is produced.
requests.packages.urllib3.disable_warnings()


def assessment_exists(api, assessment_id):
    """Check if GoPhish has at least one campaign for designated assessment.

    Args:
        api (GoPhish API): Connection to GoPhish server via the API.
        assessment_id (string): Assessment identifier to get campaigns from.

    Returns:
        boolean: Indicates if a campaign is found starting with assessment_id.
    """
    allCampaigns = api.campaigns.get()
    return any(
        campaign.name.startswith(assessment_id) for campaign in allCampaigns
    )


def export_targets(api, assessment_id):
    """Add all targets to a list.

    Achieved by pulling the group IDs for any group starting with
    the assessment id. The targets within the group are then parsed
    into a targets list of target dicts. Each target dict includes a
    sha256 hash of the target's email and assessment id with any labels.

    Args:
        api (GoPhish API): Connection to GoPhish server via the API.
        assessment_id (string): Assessment identifier to get campaigns from.

    Returns:
        List of targets from the assessment's group(s).
    """
    groupIDs = get_group_ids(api, assessment_id)

    targets = []

    for group_id in groupIDs:
        # Gets target list for parsing.
        raw_targets = api.groups.get(group_id).as_dict()["targets"]

        for raw_target in raw_targets:

            target = {
                "id": hashlib.sha256(
                    raw_target["email"].encode("utf-8")
                ).hexdigest(),
                "customer_defined_labels": {},
            }


            if "position" in raw_target:
                target["customer_defined_labels"][assessment_id] = [
                    raw_target["position"]
                ]

            targets.append(target)

    logging.info(f"{len(targets)} email targets found for assessment {assessment_id}.")

    return targets


def get_group_ids(api, assessment_id):
    """Return a list of group IDs for all groups starting with specified assessment_id."""
    rawGroup = api.groups.get()  # Holds raw list of campaigns from GoPhish.
    groups = []

    for group in rawGroup:
        group = group.as_dict()
        if group["name"].startswith(assessment_id):
            groups.append(group["id"])

    return groups


def export_campaigns(api, assessment_id):
    """Add all the campaigns' data for an assessment to a list.

    Args:
        api (GoPhish API): Connection to GoPhish server via the API.
        assessment_id (string): Assessment identifier to get campaigns from.

    Returns:
        List of the assessment's campaigns with data.
    """
    campaignIDs = get_campaign_ids(api, assessment_id)
    campaigns = [
        get_campaign_data(api, campaign_id) for campaign_id in campaignIDs
    ]


    logging.info(f"{len(campaigns)} campaigns found for assessment {assessment_id}.")

    return campaigns


def get_campaign_ids(api, assessment_id):
    """Return a list of campaign IDs for all campaigns starting with specified assessment_id."""
    rawCampaigns = api.campaigns.get()  # Holds raw list of campaigns from GoPhish.
    campaigns = []

    for campaign in rawCampaigns:
        campaign = campaign.as_dict()
        if campaign["name"].startswith(assessment_id):
            campaigns.append(campaign["id"])

    return campaigns


def get_campaign_data(api, campaign_id):
    """Return campaign metadata for the given campaign ID."""
    # Pulls the campaign data as dict from GoPhish.
    rawCampaign: dict = api.campaigns.get(campaign_id).as_dict()

    campaign = {
        "id": rawCampaign["name"],
        "start_time": rawCampaign["launch_date"],
        "end_time": rawCampaign["completed_date"],
        "url": rawCampaign["url"],
        "subject": rawCampaign["template"]["subject"],
        "template": api.templates.get(rawCampaign["template"]["id"])
        .as_dict()["name"]
        .split("-")[2],
    }

    campaign["clicks"] = get_click_data(api, campaign_id)

    # Get the e-mail send status from GoPhish.
    campaign["status"] = get_email_status(api, campaign_id)

    return campaign


def get_click_data(api, campaign_id):
    """Return a list of all clicks for a given campaign."""
    rawEvents = api.campaigns.get(campaign_id).as_dict()["timeline"]
    clicks = []

    for rawEvent in rawEvents:
        if rawEvent["message"] == "Clicked Link":
            click = {
                "user": hashlib.sha256(
                    rawEvent["email"].encode("utf-8")
                ).hexdigest()
            }


            click["source_ip"] = rawEvent["details"]["browser"]["address"]

            click["time"] = rawEvent["time"]

            click["application"] = get_application(rawEvent)

            clicks.append(click)

    return clicks


def get_email_status(api, campaign_id):
    """Return the email send status and time."""
    rawEvents = api.campaigns.get(campaign_id).as_dict()["timeline"]
    status = []
    for rawEvent in rawEvents:
        email = {}

        if rawEvent["message"] == "Email Sent":
            email["user"] = hashlib.sha256(
                rawEvent["email"].encode("utf-8")
            ).hexdigest()

            email["time"] = rawEvent["time"]

            email["status"] = "SUCCESS"

        elif rawEvent["message"] == "Error Sending Email":

            email["user"] = hashlib.sha256(
                rawEvent["email"].encode("utf-8")
            ).hexdigest()

            # Trim microseconds before converting to datetime.
            rawEvent["time"] = datetime.strptime(
                rawEvent["time"].split(".")[0], "%Y-%m-%dT%H:%M:%S"
            )
            email["time"] = rawEvent["time"]

            email["status"] = "Failed"

        if email:
            status.append(email)

    return status


def get_application(rawEvent):
    """Return application details."""
    application = {"external_ip": rawEvent["details"]["browser"]["address"]}

    # Process user agent string.
    userAgent = rawEvent["details"]["browser"]["user-agent"]
    application["name"] = httpagentparser.detect(userAgent)["platform"]["name"]
    application["version"] = httpagentparser.detect(userAgent)["platform"]["version"]

    return application


def find_unique_target_clicks_count(clicks):
    """Return the number of unique clicks in a click set."""
    uniq_users = {click["user"] for click in clicks}
    return len(uniq_users)


def write_campaign_summary(api, assessment_id):
    """Output a campaign summary report to JSON, console, and a text file."""
    campaign_ids = get_campaign_ids(api, assessment_id)
    campaign_data_template = "campaign_data.json"
    campaign_summary_json = f"{assessment_id}_campaign_data.json"
    campaign_summary_textfile = f"{assessment_id}_summary_{datetime.strftime(datetime.now(), '%Y-%m-%dT%H:%M:%S')}.txt"

    with open(campaign_data_template) as template:
        campaign_data = json.load(template)

    logging.info("Writing campaign summary report to %s", campaign_summary_textfile)
    with open(campaign_summary_textfile, "w+") as file_out:
        file_out.write(f"Campaigns for Assessment: {assessment_id}")

        regex = re.compile(r"^.*_(?P<level>level-[1-6])$")
        for campaign_id in campaign_ids:
            campaign = api.campaigns.get(campaign_id)
            if match := regex.fullmatch(campaign.name):
                level = match["level"]
            else:
                logging.warn(
                    "Encountered campaign (%s) that is unable to be processed for campaign summary export. \n"
                    "Campaign name is not properly suffixed with the campaign level number (e.g. '_level-1')\n"
                    "Skipping campaign",
                    campaign.name,
                )
                continue

            logging.info(level)
            clicks = get_click_data(api, campaign_id)

            total_clicks = api.campaigns.summary(campaign_id=campaign_id).stats.clicked
            unique_clicks = find_unique_target_clicks_count(clicks)
            if total_clicks > 0:
                percent_clicks = unique_clicks / float(total_clicks)
            else:
                percent_clicks = 0.0
            campaign_data[level]["subject"] = campaign.template.subject
            campaign_data[level]["sender"] = campaign.smtp.from_address
            campaign_data[level]["start_date"] = campaign.launch_date
            campaign_data[level]["end_date"] = campaign.completed_date
            campaign_data[level]["redirect"] = campaign.url
            campaign_data[level]["clicks"] = total_clicks
            campaign_data[level]["unique_clicks"] = unique_clicks
            campaign_data[level]["percent_clicks"] = percent_clicks

            file_out.write("\n")
            file_out.write("-" * 50)
            file_out.write("\nCampaign: %s" % campaign.name)
            file_out.write("\nSubject: %s" % campaign_data[level]["subject"])
            file_out.write("\nSender: %s" % campaign_data[level]["sender"])
            file_out.write("\nStart Date: %s" % campaign_data[level]["start_date"])
            file_out.write("\nEnd Date: %s" % campaign_data[level]["end_date"])
            file_out.write("\nRedirect: %s" % campaign_data[level]["redirect"])
            file_out.write("\nClicks: %i" % campaign_data[level]["clicks"])
            file_out.write("\nUnique Clicks: %i" % campaign_data[level]["unique_clicks"])
            file_out.write(
                "\nPercentage Clicks: %f" % campaign_data[level]["percent_clicks"]
            )

    logging.info("Writing out summary JSON to %s", campaign_summary_json)
    with open(campaign_summary_json, "w") as fp:
        json.dump(campaign_data, fp, indent=4)


def export_user_reports(api, assessment_id):
    """Build and export a user_report JSON file for each campaign in an assessment."""
    campaign_ids = get_campaign_ids(api, assessment_id)

    for campaign_id in campaign_ids:
        first_report = None
        campaign = get_campaign_data(api, campaign_id)

        # iterate over clicks and find the earliest click
        for click in campaign["clicks"]:
            click_time = datetime.strptime(
                click["time"].split(".")[0], "%Y-%m-%dT%H:%M:%S"
            )
            if first_report is None or click_time < first_report:
                first_report = click_time

        user_report_doc = {
            "customer": "",
            "assessment": assessment_id,
            "campaign": str(campaign_id),
            "first_report": datetime.strftime(
                first_report, "%Y-%m-%dT%H:%M:%S"
            )
            if first_report is not None
            else "No clicks reported",
        }

        user_report_doc["total_num_reports"] = api.campaigns.summary(
            campaign_id=campaign_id
        ).stats.clicked

        logging.info(
            f"Writing out user report for campaign {campaign_id} in assessment {assessment_id}"
        )

        with open(f"{assessment_id}_{campaign_id}_user_report_doc.json", "w") as fp:
            json.dump(user_report_doc, fp, indent=4)


def main() -> None:
    """Set up logging, connect to API, export all assessment data."""
    args: Dict[str, str] = docopt(__doc__, version=__version__)

    # Set up logging
    log_level = args["--log-level"]
    try:
        logging.basicConfig(
            format="\n%(levelname)s: %(message)s", level=log_level.upper()
        )
    except ValueError:
        logging.critical(
            f'"{log_level}"is not a valid logging level. Possible values are debug, info, warning, and error.'
        )
        sys.exit(1)

    else:
        # Connect to API
        try:
            api = connect_api(args["API_KEY"], args["SERVER"])
            logging.debug(f'Connected to: {args["SERVER"]}')
        except Exception as e:
            logging.critical(e.args[0])
            sys.exit(1)

    if assessment_exists(api, args["ASSESSMENT_ID"]):
        assessment_dict: Dict = {"targets": export_targets(api, args["ASSESSMENT_ID"])}

        # Add campaigns list to the assessment dict.
        assessment_dict["campaigns"] = export_campaigns(api, args["ASSESSMENT_ID"])

        with open(f'data_{args["ASSESSMENT_ID"]}.json', "w") as fp:
            json.dump(assessment_dict, fp, indent=4)

        logging.info(f'Data written to data_{args["ASSESSMENT_ID"]}.json')

        export_user_reports(api, args["ASSESSMENT_ID"])
        write_campaign_summary(api, args["ASSESSMENT_ID"])
    else:
        logging.error(
            f'Assessment "{args["ASSESSMENT_ID"]}" does not exist in GoPhish.'
        )
        sys.exit(1)
