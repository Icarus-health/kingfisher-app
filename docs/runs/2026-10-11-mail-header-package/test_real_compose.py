from pathlib import Path
import ast,os,subprocess,json,tempfile
root=Path(__file__).parent;tree=ast.parse((root/'install.py').read_text())
ns={'os':os};exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='compose_environment'],type_ignores=[]),'<actual compose environment>','exec'),ns)
os.environ.update(ICARUS_PROVIDER='unwanted-cloud',LLM_API_KEY='unwanted-key',KINGFISHER_IMAGE='unwanted-image',ICARUS_MODEL='unwanted-model',COMPOSE_PROJECT_NAME='unwanted-project')
with tempfile.TemporaryDirectory(prefix='kingfisher-synthetic-compose-') as d:
 config=Path(d)/'synthetic.env';config.write_text('ICARUS_SIDECAR_TOKEN=synthetic-token\nICARUS_SECRETS_PASSPHRASE=synthetic-passphrase\nICARUS_PROVIDER=local\nICARUS_MODEL=synthetic-local-model\nLLM_API_KEY=\nKINGFISHER_IMAGE=ghcr.io/icarus-health/kingfisher-app:1.0.6-preview.f858681\n')
 raw=subprocess.check_output(['/opt/homebrew/bin/docker','compose','-p','kingfisher-synthetic','-f',str(root/'deploy/compose.app.yaml'),'--env-file',str(config),'config','--format','json'],text=True,env=ns['compose_environment']())
 parsed=json.loads(raw);service=parsed['services']['kingfisher']
 assert service['image']=='ghcr.io/icarus-health/kingfisher-app:1.0.6-preview.f858681'
 assert service['environment']['ICARUS_PROVIDER']=='local'
 assert service['environment']['ICARUS_MODEL']=='synthetic-local-model'
 assert service['environment']['LLM_API_KEY']==''
 assert parsed['name']=='kingfisher-synthetic'
print(json.dumps({'actual_docker_compose_config_only':True,'ambient_provider_model_key_image_overrides_ignored':True,'synthetic_env_only':True,'no_container_started':True}))
