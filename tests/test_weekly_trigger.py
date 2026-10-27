"""Verify scheduler events cannot select other instances or arbitrary commands."""
import importlib.util
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch


class WeeklyTrigger(unittest.TestCase):
    def setUp(self):
        self.ec2, self.ssm = Mock(), Mock()
        self.sdk = types.SimpleNamespace(client=lambda service:{'ec2':self.ec2,'ssm':self.ssm}[service])
        spec=importlib.util.spec_from_file_location('weekly_handler',Path(__file__).resolve().parents[1]/'infra/aws/weekly/handler.py')
        self.module=importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules,{'boto3':self.sdk}): spec.loader.exec_module(self.module)
        self.env={'END_DATE':'2099-01-01T00:00:00Z','INSTANCE_ID':'fixed-instance','SSM_DOCUMENT':'fixed-document'}

    def test_fixed_destination_ignores_event_commands(self):
        self.ec2.describe_instances.return_value={'Reservations':[{'Instances':[{'State':{'Name':'running'}}]}]}
        self.ssm.send_command.return_value={'Command':{'CommandId':'command-id'}}
        with patch.dict(os.environ,self.env):
            result=self.module.handler({'instance_id':'other','command':'unexpected'},None)
        self.assertEqual(result['status'],'submitted')
        args=self.ssm.send_command.call_args.kwargs
        self.assertEqual(args['InstanceIds'],['fixed-instance'])
        self.assertEqual(args['DocumentName'],'fixed-document')
        self.assertNotIn('Parameters',args)

    def test_stopped_instance_is_not_started(self):
        self.ec2.describe_instances.return_value={'Reservations':[{'Instances':[{'State':{'Name':'stopped'}}]}]}
        with patch.dict(os.environ,self.env): result=self.module.handler({},None)
        self.assertEqual(result['status'],'skipped')
        self.ec2.start_instances.assert_not_called()
        self.ssm.send_command.assert_not_called()

    def test_expiry_blocks_dispatch(self):
        with patch.dict(os.environ,{**self.env,'END_DATE':'2020-01-01T00:00:00Z'}):
            result=self.module.handler({},None)
        self.assertEqual(result['reason'],'collection_deadline_reached')
        self.ec2.describe_instances.assert_not_called()
        self.ssm.send_command.assert_not_called()


if __name__=='__main__': unittest.main()
