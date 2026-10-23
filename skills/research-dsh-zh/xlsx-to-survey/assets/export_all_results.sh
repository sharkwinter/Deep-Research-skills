#!/bin/bash
# Export all survey results (HTML + raw data). Called by cron every 10 min.
# Unified method: export_survey_results2.py (spec-based) for every survey.
set -u
cd /root/Working/polling/deploy

/usr/bin/python3 export_survey_results2.py /root/Working/polling/polls/macao/specs/ai_coding_survey.json >> export_results.log 2>&1
/usr/bin/python3 export_survey_results2.py /root/Working/polling/polls/macao/specs/tech_enterprise_survey.json >> export_results.log 2>&1
/usr/bin/python3 export_survey_results2.py /root/Working/polling/polls/macao/specs/university_survey.json >> export_results.log 2>&1
/usr/bin/python3 export_survey_results2.py /root/Working/polling/polls/macao/specs/macao_ai_compute_survey.json >> export_results.log 2>&1
/usr/bin/python3 export_survey_results2.py /root/Working/polling/polls/macao/specs/ai_transformation_survey.json >> export_results.log 2>&1
/usr/bin/python3 export_survey_results2.py /root/Working/polling/polls/macao/specs/public_admin_survey.json >> export_results.log 2>&1
