"""Initial private dictionary platform schema."""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        "\nCREATE TABLE audit_events (\n\tid VARCHAR NOT NULL, \n\tworkspace_id VARCHAR NOT NULL, \n\tactor_id VARCHAR NOT NULL, \n\taction VARCHAR NOT NULL, \n\tresource_id VARCHAR NOT NULL, \n\tdetails JSON NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id)\n)\n\n"
    )
    op.execute("CREATE INDEX ix_audit_events_workspace_id ON audit_events (workspace_id)")
    op.execute(
        "\nCREATE TABLE identities (\n\tid VARCHAR NOT NULL, \n\tname VARCHAR NOT NULL, \n\ttoken_hash VARCHAR NOT NULL, \n\tworkspace_id VARCHAR NOT NULL, \n\trole VARCHAR NOT NULL, \n\tactive BOOLEAN NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (token_hash)\n)\n\n"
    )
    op.execute("CREATE INDEX ix_identities_workspace_id ON identities (workspace_id)")
    op.execute(
        "\nCREATE TABLE languages (\n\tid VARCHAR NOT NULL, \n\tworkspace_id VARCHAR NOT NULL, \n\tslug VARCHAR NOT NULL, \n\tname VARCHAR NOT NULL, \n\talternate_names JSON NOT NULL, \n\tiso_code VARCHAR, \n\tdescription TEXT NOT NULL, \n\tdefault_dialect VARCHAR NOT NULL, \n\torthography_notes TEXT NOT NULL, \n\tsource_community TEXT NOT NULL, \n\tgovernance_notes TEXT NOT NULL, \n\tvisibility VARCHAR NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (workspace_id, slug)\n)\n\n"
    )
    op.execute("CREATE INDEX ix_languages_workspace_id ON languages (workspace_id)")
    op.execute(
        "\nCREATE TABLE datasets (\n\tid VARCHAR NOT NULL, \n\tlanguage_id VARCHAR NOT NULL, \n\tversion INTEGER NOT NULL, \n\tsource_ids JSON NOT NULL, \n\tgovernance JSON NOT NULL, \n\tobject_key VARCHAR NOT NULL, \n\tsha256 VARCHAR NOT NULL, \n\tmanifest JSON NOT NULL, \n\tseed INTEGER NOT NULL, \n\tgeneration_version VARCHAR NOT NULL, \n\tentry_count INTEGER NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (language_id, version), \n\tFOREIGN KEY(language_id) REFERENCES languages (id)\n)\n\n"
    )
    op.execute("CREATE INDEX ix_datasets_language_id ON datasets (language_id)")
    op.execute(
        "\nCREATE TABLE negative_corpora (\n\tid VARCHAR NOT NULL, \n\tlanguage_id VARCHAR NOT NULL, \n\tname VARCHAR NOT NULL, \n\tgovernance JSON NOT NULL, \n\tobject_key VARCHAR NOT NULL, \n\tsha256 VARCHAR NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(language_id) REFERENCES languages (id)\n)\n\n"
    )
    op.execute("CREATE INDEX ix_negative_corpora_language_id ON negative_corpora (language_id)")
    op.execute(
        "\nCREATE TABLE sources (\n\tid VARCHAR NOT NULL, \n\tlanguage_id VARCHAR NOT NULL, \n\tfilename VARCHAR NOT NULL, \n\tobject_key VARCHAR NOT NULL, \n\tsha256 VARCHAR NOT NULL, \n\tgovernance JSON NOT NULL, \n\tcolumns JSON NOT NULL, \n\tmapping JSON NOT NULL, \n\tnormalization JSON NOT NULL, \n\tquality JSON NOT NULL, \n\tstatus VARCHAR NOT NULL, \n\tvisibility VARCHAR NOT NULL, \n\tapproved_by VARCHAR, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(language_id) REFERENCES languages (id)\n)\n\n"
    )
    op.execute("CREATE INDEX ix_sources_language_id ON sources (language_id)")
    op.execute(
        "\nCREATE TABLE entries (\n\tid VARCHAR NOT NULL, \n\tlanguage_id VARCHAR NOT NULL, \n\tsource_id VARCHAR NOT NULL, \n\trow_number INTEGER NOT NULL, \n\toriginal_row JSON NOT NULL, \n\theadword TEXT NOT NULL, \n\tnormalized_headword TEXT NOT NULL, \n\tdefinitions JSON NOT NULL, \n\talternate_spellings JSON NOT NULL, \n\tpart_of_speech VARCHAR NOT NULL, \n\tdialect VARCHAR NOT NULL, \n\texamples JSON NOT NULL, \n\tnotes TEXT NOT NULL, \n\tsource TEXT NOT NULL, \n\tentry_metadata JSON NOT NULL, \n\tissues JSON NOT NULL, \n\tapproved BOOLEAN NOT NULL, \n\ttraining_eligible BOOLEAN NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(language_id) REFERENCES languages (id), \n\tFOREIGN KEY(source_id) REFERENCES sources (id)\n)\n\n"
    )
    op.execute("CREATE INDEX ix_entries_language_id ON entries (language_id)")
    op.execute("CREATE INDEX ix_entries_source_id ON entries (source_id)")
    op.execute(
        "\nCREATE TABLE training_runs (\n\tid VARCHAR NOT NULL, \n\tlanguage_id VARCHAR NOT NULL, \n\tdataset_id VARCHAR NOT NULL, \n\ttask VARCHAR NOT NULL, \n\tbase_model VARCHAR NOT NULL, \n\tbase_model_revision VARCHAR NOT NULL, \n\thyperparameters JSON NOT NULL, \n\trandom_seed INTEGER NOT NULL, \n\tgit_commit VARCHAR NOT NULL, \n\tenvironment JSON NOT NULL, \n\tstarted_at TIMESTAMP WITH TIME ZONE, \n\tcompleted_at TIMESTAMP WITH TIME ZONE, \n\theartbeat_at TIMESTAMP WITH TIME ZONE, \n\tmetrics JSON NOT NULL, \n\tartifact_location VARCHAR, \n\tstatus VARCHAR NOT NULL, \n\tcancel_requested BOOLEAN NOT NULL, \n\terror TEXT, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(language_id) REFERENCES languages (id), \n\tFOREIGN KEY(dataset_id) REFERENCES datasets (id)\n)\n\n"
    )
    op.execute("CREATE INDEX ix_training_runs_language_id ON training_runs (language_id)")
    op.execute("CREATE INDEX ix_training_runs_status ON training_runs (status)")
    op.execute(
        "\nCREATE TABLE models (\n\tid VARCHAR NOT NULL, \n\tlanguage_id VARCHAR NOT NULL, \n\ttraining_run_id VARCHAR NOT NULL, \n\tdataset_id VARCHAR NOT NULL, \n\ttask VARCHAR NOT NULL, \n\tversion INTEGER NOT NULL, \n\tbase_model VARCHAR NOT NULL, \n\tbase_model_revision VARCHAR NOT NULL, \n\tmetrics JSON NOT NULL, \n\tartifact VARCHAR NOT NULL, \n\tartifact_sha256 VARCHAR NOT NULL, \n\tstatus VARCHAR NOT NULL, \n\tvisibility VARCHAR NOT NULL, \n\texperimental BOOLEAN NOT NULL, \n\tapproved_by VARCHAR, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (language_id, task, version), \n\tFOREIGN KEY(language_id) REFERENCES languages (id), \n\tUNIQUE (training_run_id), \n\tFOREIGN KEY(training_run_id) REFERENCES training_runs (id), \n\tFOREIGN KEY(dataset_id) REFERENCES datasets (id)\n)\n\n"
    )
    op.execute("CREATE INDEX ix_models_language_id ON models (language_id)")
    op.execute(
        "\nCREATE TABLE run_events (\n\tid SERIAL NOT NULL, \n\trun_id VARCHAR NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tmessage TEXT NOT NULL, \n\tdata JSON NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(run_id) REFERENCES training_runs (id)\n)\n\n"
    )
    op.execute("CREATE INDEX ix_run_events_run_id ON run_events (run_id)")
    op.execute(
        "\nCREATE TABLE concept_vectors (\n\tid VARCHAR NOT NULL, \n\tlanguage_id VARCHAR NOT NULL, \n\tmodel_id VARCHAR NOT NULL, \n\tentry_id VARCHAR NOT NULL, \n\tkind VARCHAR NOT NULL, \n\tconcept JSON NOT NULL, \n\tembedding VECTOR NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (model_id, entry_id, kind), \n\tFOREIGN KEY(language_id) REFERENCES languages (id), \n\tFOREIGN KEY(model_id) REFERENCES models (id)\n)\n\n"
    )
    op.execute("CREATE INDEX ix_concept_vectors_language_id ON concept_vectors (language_id)")
    op.execute("CREATE INDEX ix_concept_vectors_model_id ON concept_vectors (model_id)")
    op.execute(
        "\nCREATE TABLE deployments (\n\tid VARCHAR NOT NULL, \n\tlanguage_id VARCHAR NOT NULL, \n\ttask VARCHAR NOT NULL, \n\tmodel_id VARCHAR NOT NULL, \n\tdeployed_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (language_id, task), \n\tFOREIGN KEY(language_id) REFERENCES languages (id), \n\tFOREIGN KEY(model_id) REFERENCES models (id)\n)\n\n"
    )


def downgrade():
    op.drop_table("deployments")
    op.drop_table("concept_vectors")
    op.drop_table("run_events")
    op.drop_table("models")
    op.drop_table("training_runs")
    op.drop_table("entries")
    op.drop_table("sources")
    op.drop_table("negative_corpora")
    op.drop_table("datasets")
    op.drop_table("languages")
    op.drop_table("identities")
    op.drop_table("audit_events")
