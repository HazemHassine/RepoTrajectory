CREATE TABLE contributors (
	id SERIAL NOT NULL, 
	github_id BIGINT, 
	login VARCHAR(255) NOT NULL, 
	avatar_url TEXT, 
	html_url TEXT, 
	contributor_type VARCHAR(50), 
	PRIMARY KEY (id), 
	UNIQUE (github_id)
)

;
CREATE UNIQUE INDEX ix_contributors_login ON contributors (login);

CREATE TABLE repositories (
	id SERIAL NOT NULL, 
	github_id BIGINT NOT NULL, 
	owner VARCHAR(255) NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	full_name VARCHAR(511) NOT NULL, 
	description TEXT, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	pushed_at TIMESTAMP WITH TIME ZONE, 
	stars INTEGER NOT NULL, 
	forks INTEGER NOT NULL, 
	watchers INTEGER NOT NULL, 
	open_issues INTEGER NOT NULL, 
	default_branch VARCHAR(255) NOT NULL, 
	primary_language VARCHAR(100), 
	license VARCHAR(100), 
	archived BOOLEAN NOT NULL, 
	last_ingested_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_repository_owner_name UNIQUE (owner, name)
)

;
CREATE UNIQUE INDEX ix_repositories_github_id ON repositories (github_id);
CREATE INDEX ix_repositories_owner ON repositories (owner);
CREATE UNIQUE INDEX ix_repositories_full_name ON repositories (full_name);

CREATE TABLE commits (
	sha VARCHAR(40) NOT NULL, 
	repository_id INTEGER NOT NULL, 
	author_id INTEGER, 
	author_login VARCHAR(255), 
	committed_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (sha, repository_id), 
	FOREIGN KEY(repository_id) REFERENCES repositories (id) ON DELETE CASCADE, 
	FOREIGN KEY(author_id) REFERENCES contributors (id)
)

;
CREATE INDEX ix_commits_committed_at ON commits (committed_at);
CREATE INDEX ix_commit_repo_committed ON commits (repository_id, committed_at);
CREATE INDEX ix_commits_repository_id ON commits (repository_id);

CREATE TABLE issues (
	repository_id INTEGER NOT NULL, 
	number INTEGER NOT NULL, 
	author_login VARCHAR(255), 
	state VARCHAR(20) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	closed_at TIMESTAMP WITH TIME ZONE, 
	comments INTEGER NOT NULL, 
	labels JSON NOT NULL, 
	PRIMARY KEY (repository_id, number), 
	FOREIGN KEY(repository_id) REFERENCES repositories (id) ON DELETE CASCADE
)

;
CREATE INDEX ix_issues_closed_at ON issues (closed_at);
CREATE INDEX ix_issue_repo_created ON issues (repository_id, created_at);
CREATE INDEX ix_issues_created_at ON issues (created_at);
CREATE INDEX ix_issue_repo_updated ON issues (repository_id, updated_at);
CREATE INDEX ix_issue_repo_closed ON issues (repository_id, closed_at);

CREATE TABLE metric_snapshots (
	id SERIAL NOT NULL, 
	repository_id INTEGER NOT NULL, 
	calculated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	window_days INTEGER NOT NULL, 
	momentum_score FLOAT NOT NULL, 
	health_score FLOAT NOT NULL, 
	bus_factor_risk FLOAT NOT NULL, 
	components JSON NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(repository_id) REFERENCES repositories (id) ON DELETE CASCADE
)

;
CREATE INDEX ix_metric_snapshots_calculated_at ON metric_snapshots (calculated_at);
CREATE INDEX ix_metric_repo_calculated ON metric_snapshots (repository_id, calculated_at);
CREATE INDEX ix_metric_snapshots_repository_id ON metric_snapshots (repository_id);

CREATE TABLE pull_requests (
	repository_id INTEGER NOT NULL, 
	number INTEGER NOT NULL, 
	author_login VARCHAR(255), 
	state VARCHAR(20) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	closed_at TIMESTAMP WITH TIME ZONE, 
	merged_at TIMESTAMP WITH TIME ZONE, 
	additions INTEGER, 
	deletions INTEGER, 
	changed_files INTEGER, 
	PRIMARY KEY (repository_id, number), 
	FOREIGN KEY(repository_id) REFERENCES repositories (id) ON DELETE CASCADE
)

;
CREATE INDEX ix_pull_requests_created_at ON pull_requests (created_at);
CREATE INDEX ix_pr_repo_created ON pull_requests (repository_id, created_at);
CREATE INDEX ix_pull_requests_merged_at ON pull_requests (merged_at);
CREATE INDEX ix_pr_repo_updated ON pull_requests (repository_id, updated_at);
CREATE INDEX ix_pr_repo_merged ON pull_requests (repository_id, merged_at);

CREATE TABLE releases (
	repository_id INTEGER NOT NULL, 
	github_id BIGINT NOT NULL, 
	tag VARCHAR(255) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	published_at TIMESTAMP WITH TIME ZONE, 
	prerelease BOOLEAN NOT NULL, 
	draft BOOLEAN NOT NULL, 
	PRIMARY KEY (repository_id, github_id), 
	FOREIGN KEY(repository_id) REFERENCES repositories (id) ON DELETE CASCADE
)

;
CREATE INDEX ix_release_repo_published ON releases (repository_id, published_at);
CREATE INDEX ix_releases_created_at ON releases (created_at);

CREATE TABLE repository_contributors (
	repository_id INTEGER NOT NULL, 
	contributor_id INTEGER NOT NULL, 
	contributions INTEGER NOT NULL, 
	last_seen_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (repository_id, contributor_id), 
	FOREIGN KEY(repository_id) REFERENCES repositories (id) ON DELETE CASCADE, 
	FOREIGN KEY(contributor_id) REFERENCES contributors (id) ON DELETE CASCADE
)

;


CREATE TABLE repository_languages (
	repository_id INTEGER NOT NULL, 
	language VARCHAR(100) NOT NULL, 
	bytes BIGINT NOT NULL, 
	PRIMARY KEY (repository_id, language), 
	FOREIGN KEY(repository_id) REFERENCES repositories (id) ON DELETE CASCADE
)

;


CREATE TABLE repository_snapshots (
	id SERIAL NOT NULL, 
	repository_id INTEGER NOT NULL, 
	captured_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	stars INTEGER NOT NULL, 
	forks INTEGER NOT NULL, 
	open_issues INTEGER NOT NULL, 
	watchers INTEGER NOT NULL, 
	contributor_count INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(repository_id) REFERENCES repositories (id) ON DELETE CASCADE
)

;
CREATE INDEX ix_repository_snapshots_captured_at ON repository_snapshots (captured_at);
CREATE INDEX ix_repository_snapshots_repository_id ON repository_snapshots (repository_id);
CREATE INDEX ix_snapshot_repo_captured ON repository_snapshots (repository_id, captured_at);

CREATE TABLE repository_topics (
	repository_id INTEGER NOT NULL, 
	topic VARCHAR(100) NOT NULL, 
	PRIMARY KEY (repository_id, topic), 
	FOREIGN KEY(repository_id) REFERENCES repositories (id) ON DELETE CASCADE
)

;
