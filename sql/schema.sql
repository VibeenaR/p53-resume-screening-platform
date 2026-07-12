-- PHASE 4: Azure SQL Database Schema
-- Run this against ResumeScreeningDB (README Phase 0.3, step 5)
-- via Azure Data Studio, SSMS, or:
--   sqlcmd -S resume-sql-server.database.windows.net -d ResumeScreeningDB -U sqladmin -P "<pwd>" -i schema.sql

CREATE TABLE JobPostings (
    JobID INT IDENTITY(1,1) PRIMARY KEY,
    Title NVARCHAR(200) NOT NULL,
    Description NVARCHAR(MAX) NOT NULL,
    RequiredSkills NVARCHAR(MAX),      -- comma-separated for simplicity
    MinYearsExperience INT DEFAULT 0,
    CreatedAt DATETIME2 DEFAULT SYSUTCDATETIME()
);

CREATE TABLE Candidates (
    CandidateID INT IDENTITY(1,1) PRIMARY KEY,
    FullName NVARCHAR(200),
    Email NVARCHAR(200),
    Phone NVARCHAR(50),
    ResumeBlobPath NVARCHAR(500),      -- path in Blob Storage
    ParsedText NVARCHAR(MAX),
    ExtractedSkills NVARCHAR(MAX),     -- JSON array as string
    CreatedAt DATETIME2 DEFAULT SYSUTCDATETIME()
);

CREATE TABLE Applications (
    ApplicationID INT IDENTITY(1,1) PRIMARY KEY,
    CandidateID INT NOT NULL FOREIGN KEY REFERENCES Candidates(CandidateID),
    JobID INT NOT NULL FOREIGN KEY REFERENCES JobPostings(JobID),
    SemanticSimilarity FLOAT,
    SkillOverlapScore FLOAT,
    ExperienceMatchScore FLOAT,
    FinalRankScore FLOAT,
    Status NVARCHAR(50) DEFAULT 'Received',  -- Received, Shortlisted, Rejected, Interviewed
    AppliedAt DATETIME2 DEFAULT SYSUTCDATETIME()
);

-- Index to speed up "top candidates per job" queries for the dashboard
CREATE INDEX IX_Applications_JobID_Score
    ON Applications (JobID, FinalRankScore DESC);
