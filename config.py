# some variables which is useful to twicking the automation's settings


# the list of users who receives a copy of emails
from datetime import timedelta


email_cc_list = [
    # 'idelia@junehomes.com',
    # 'it_support_agent_emails@junehomes.com',
    ]

# for test
# email_cc_list = ['test@m.com',
#                  'ilya.konovalov@junehomes.com',
#                  '456@123.com'
#                  ]

# adding hours for email sending to 00:00 UTC
countdown_for_it_content = timedelta(hours=4)
countdown_for_others_depts = timedelta(hours=12)



# for frontapp
# when the new role on Frontapp is added - it should be also added to this dictionary
roles_dict = {
            "Sales regular user": "tea_14r7o",
            "Team member": "tea_14rd0",
            "Success team lead": "tea_14res",
            "Nutiliti Tiger Team": "tea_15c1w",
            "Support Nightshift Agent": "tea_17guc",
            "Support Onboarding Agent": "tea_17h1g",
            "Resolutions Team Agent": "tea_17upw",
            "Support Team Leader": "tea_17utg",
            "Landlord Team Agent": "tea_17uv8",
            "Collections Member": "tea_18q84",
            }

google_license_skus = {
    "G Suite Business": "Google-Apps-Unlimited",
    "Google Workspace Business Plus": "1010020025"
    # "Google Workspace Enterprise Plus": "1010020020",
}

# JuneHomes instance ID - old / unused
# instance_id = 'a016cbe1-24bf-483a-b2cf-a73f2f389cb4'

# USRENATPS
instance_id = 'eed49c00-05b4-4446-9156-f4b698bf3dd7'
