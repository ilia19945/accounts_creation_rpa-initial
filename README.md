# 🚀 Accounts creation RPA (Initial project) description:
check [Updates](https://github.com/ilia19945/accounts_creation_automation/readme.md#53) section
Accounts creation RPA intended to automate the IT-Support department routine tasks of:
1. Creating accounts for new hires
2. Adding permissions according to the role
3. Providing new hires with the new account information and service notifications being created for them.

# ✅ The RPA system helped:
-  To decrease the time IT support agents spend to create accounts and schedule emails to new hires from ~1.5hours to -> ~10-15 min
-  To exclude human errors during the accounts creation
- To implement a roles model - a source of truth for the whole company (which helped to make isec stronger, and make the communication between IT and other departments explicit and stateful)  

# 🎯 The automation achieved using:
1. FastAPI framework (as the main server)
2. Celery and Redis (to decrease the load to the main process) + Flower as GUI for Celery task canceling.
3. all services run using docker-compose
4. ~~ELK for monitoring and logging~~ (not used to decrease EC2 machine tier) -> python module logging to collect logs
   
- The automation flows are triggered by an incoming Jira webhook (I used ngrok for tunneling), which sends the webhook body to the automation.   
  - The Jira webhook is attached to a particular Jira filter and the webhook is triggered when the agent switches the ticket status or when the IT support agent updates the ticket description.  
    - The automation process the request body according to the business logic and sends requests to the necessary service for account creation.   
      - When a successful result is received from the service the automation schedules the email message to be sent on the employee start date (using Celery tasks) and notifies the IT support agent with the necessary information as well as with performing additional actions which couldn't be automated.  
      -  Otherwise, if a request to the service is failed - the request result is posted to the Jira ticket in a pretty form so that the agent can make necessary changes.  

# ➕ A role description is taken from the Notion Databases, supporting:
1. Role inheritance
   - Example: Senior dev will receive all permissions from Middle dev Junior devs
3. Services matching
   - Example: Service configs will be updated automatically when the role's new description is requested
5. Errors notification
   - Service will notify the IT support agent when there is an error in the role description
7. Human-facing role tree posted as a comment to Jira ticket
   - Service will explicitly show the structure of the services being posted to the Jira ticket when the role config is built

# ⚙ Service successfully integrated with: 
1. **Google Workspace**
   - Admin API (to create accounts, assign licenses, add to Google groups, assign attributes necessary for Zendesk SAML auth)
   - Gmail (to send emails),
   - Calendar (to add new hires to teams' calendars)
3. **Amazon Connect** (to create accounts and to assign routing/security profiles_  
5. **Zendesk** to check account existence (moved to Google Workspace thought SAML later)
7. **Jira** (to notify IT support Agents about the automation results)
9. **Frontapp** (to create accounts / assigned licenses / assigned teammate templates)
11. **Notion** (the main source of truth to get a role's services with configs for a requested role)
   
----------------------------------------------------------------------------
# 🔥 Updates and the project final:
* plans and not implemented functionality:
1. User accounts suspension when the user is terminated
2. Changing roles when the user is promoted or his /her role in the company changes (i.e. removing all permissions according to the current role -> assigning new permissions according to the target role)

🏁**Project Final:**  
Although the project is pretty heavy by the moment I'm writing this - it was written when I had very limited knowledge of coding, therefore some constructs in the code may be suboptimal or outdated. So, a short while ago, I decided to revamp the code, but, unfortunately, I fell under a wave of layoffs and did not finish the code revamp. Lots of logic depended on the integrations and I decided not to touch them as not being able to test them properly. 

UPD. link to a new repo: [accounts_creation_rpa-revamp](https://github.com/ilia19945/accounts_creation_rpa-revamp/tree/master).  

---------------------------------------------------------------------------  

This project - is my first complete, properly build, and fully integrated business processes RPA, which helped me not only to learn coding with Python in general, FastAPI framework, Celery + redis, Containerization (via Docker / docker-compose), using AWS for Deployment and many-many more,  
**But what I consider more important was to make my colleagues' life easier.  And I can't be more grateful to JuneHomes for this opportunity.**


