import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).parents[1]
spec=importlib.util.spec_from_file_location('read_check',ROOT/'scripts/diagnostics/check-chat-server-read.py')
check=importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)

class ReadCheckTests(unittest.TestCase):
    def test_program_outputs_only_metadata_using_pinned_module_graph(self):
        sources={
            'lib/chat-controls.mjs':'export const fixture=true;',
            'lib/host-agent.js':'export async function hostSnapshot(){return {secret:"not exported"}}; export async function hostInspect(){};',
            'lib/local-server-statistics.mjs':"import {fixture} from './chat-controls.mjs'; export async function localServerStatistics(){return {files:2,text:'private fixture'}};",
        }
        def run(args,**kwargs):
            return sources[args[-1].split(':',1)[1]]
        with patch.object(check,'run',side_effect=run):
            source=check.program('a'*40)
        result=subprocess.run(['node','--input-type=module','-'],input=source,text=True,capture_output=True,check=True)
        self.assertEqual(json.loads(result.stdout),{'snapshot_available':True,'statistics_complete':True,'files':2})
        self.assertNotIn('private fixture',result.stdout)
        self.assertNotIn('not exported',result.stdout)

    def test_interruption_persists_failed_gate_even_when_production_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'releases').mkdir();compose=root/'compose.yml';compose.write_text('synthetic')
            state={'vector-app':'id|'+check.CURRENT_IMAGE+'|started|true'}
            with patch.object(check,'ROOT',root),patch.object(check,'COMPOSE',(compose,)),patch.object(check,'snapshot',return_value=state),\
                 patch.object(check.os,'geteuid',return_value=0),patch.dict(os.environ,{'VECTOR_CHAT_REV':'a'*40}),\
                 patch.object(check,'program',return_value='synthetic'),patch.object(check,'run',side_effect=KeyboardInterrupt),\
                 patch('builtins.print'):
                with self.assertRaisesRegex(RuntimeError,'READ_CHECK_FAILED'):check.main()
            result=json.loads(next((root/'releases').glob('*/result.json')).read_text())
            self.assertFalse(result['passed']);self.assertTrue(result['production_unchanged'])
            self.assertEqual(result['error'],'KeyboardInterrupt')

if __name__=='__main__':unittest.main()
