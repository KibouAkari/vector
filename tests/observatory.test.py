import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts/collectors/observatory'))
from core import conntrack_line,nginx_line,HostSampler,socket_line
from nginx_config import instrument,listed_files

class Observatory(unittest.TestCase):
    def test_original_nat_tuple_game_and_owned_destinations(self):
        line='[NEW] tcp 6 100 ESTABLISHED src=198.51.100.9 dst=203.0.113.5 sport=52123 dport=25565 src=172.18.0.2 dst=198.51.100.9 sport=25565 dport=52123 id=48'
        event=conntrack_line(line,{'tcp/25565':'Game'},{'203.0.113.5'},'fixture')
        self.assertEqual(event['destinationIp'],'203.0.113.5')
        self.assertEqual(event['sourceIp'],'198.51.100.9')
        self.assertEqual(event['kind'],'connection-open')
        self.assertIsNone(conntrack_line(line,{'tcp/25565':'Game'},{'203.0.113.6'},'fixture'))
        self.assertEqual(conntrack_line(line.replace('[NEW]','[DESTROY]'),{'tcp/25565':'Game'},{'203.0.113.5'},'fixture')['kind'],'connection-close')
    def test_ipv6_socket_and_udp_flow(self):
        row=socket_line('0 0 [2001:db8::1]:443 [2001:db8::2]:52123',{'tcp/443':'HTTPS'},{'2001:db8::1'},'fixture')
        self.assertEqual(row['sourceIp'],'2001:db8::2')
        row=conntrack_line('udp 17 30 src=198.51.100.2 dst=203.0.113.1 sport=50231 dport=19132 src=172.18.0.2 dst=198.51.100.2 sport=19132 dport=50231',{'udp/19132':'Game'},{'203.0.113.1'},'fixture')
        self.assertEqual(row['transport'],'udp')
        self.assertEqual(row['state'],'flow')
    def test_nginx_retains_only_approved_metadata(self):
        source={'time_iso8601':datetime.now(timezone.utc).isoformat(),'remote_addr':'198.51.100.10','server_name':'site.example','request_method':'GET','status':'200','request_time':'.025','bytes_sent':'42','request_uri':'/secret-path?token=private','body':'password','authorization':'bearer example'}
        row=nginx_line(json.dumps(source),{'site.example':'Website'})
        self.assertEqual(row['durationMs'],25)
        for key in ('path','request_uri','body','authorization'):self.assertNotIn(key,row)
        self.assertIsNone(nginx_line('not json',{}))
        self.assertIsNone(nginx_line(json.dumps(source),{}))
    def test_cpu_delta_and_ram_use_real_host_samples(self):
        with tempfile.TemporaryDirectory() as value:
            path=Path(value)
            (path/'stat').write_text('cpu 100 0 0 900 0 0 0 0 20 0\n')
            (path/'meminfo').write_text('MemTotal: 1000 kB\nMemAvailable: 400 kB\n')
            sampler=HostSampler(proc=value)
            self.assertIsNone(sampler.sample()['cpuPercent'])
            (path/'stat').write_text('cpu 125 0 0 975 0 0 0 0 20 0\n')
            result=sampler.sample()
            self.assertEqual(result['cpuPercent'],25)
            self.assertEqual(result['memory']['totalBytes'],1024000)
    def test_nginx_hook_ignores_quoted_content_and_logging_off(self):
        source='events {}\nhttp { access_log /old.log combined; server { access_log off; location / { return 200 "access_log and { ; }"; } } server { access_log /site.log; } }'
        updated,changed=instrument(source,'/var/log/vector-observatory/metadata.log',True)
        self.assertTrue(changed)
        self.assertEqual(updated.count('vector_metadata buffer='),2)
        self.assertIn('access_log off;',updated)
        self.assertIn('"access_log and { ; }"',updated)
        self.assertEqual(instrument(updated,'/ignored',True),(updated,False))
        self.assertEqual(listed_files('# configuration file /etc/nginx/nginx.conf:\n'),['/etc/nginx/nginx.conf'])
    def test_service_never_receives_docker_socket_or_root_identity(self):
        unit=(ROOT/'scripts/collectors/observatory/vector-observatory.service').read_text()
        self.assertIn('User=vector-observatory',unit)
        self.assertIn('ProtectSystem=strict',unit)
        self.assertIn('LoadCredential=',unit)
        self.assertNotIn('docker.sock',unit)

if __name__=='__main__':unittest.main()
