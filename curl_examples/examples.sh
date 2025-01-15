curl --json @reps_in_study.json https://madc.vdjbase.org/airr/v1/repertoire
curl --json @all_reps.json https://madc.vdjbase.org/airr/v1/repertoire
curl -OJ https://madc.vdjbase.org/airr/v1/repertoire/9_IGH
curl -OJ --json @study.json https://madc.vdjbase.org/airr/v1/rearrangement
curl -OJ --json "{""filters"": {""op"": ""="",	""content"": {""field"": ""repertoire_id"", ""value"": ""99_IGH""}}, ""format"": ""tsv""}" https://madc.vdjbase.org/airr/v1/rearrangement
