Feature: End-to-end processing pipeline
  As an archive maintainer
  I want the pipeline to process uploaded photos predictably
  So that metadata and export artifacts are generated with traceability

  Scenario: Successful pipeline with review approval and export
    Given a temporary Caipture test environment
    And valid front and back PNG inputs with OCR sidecar text "Summer 1934 Enschede family"
    When I create a new processing job
    And I run the CV, OCR, and metadata workers once
    Then the job status should be "review_required"
    When I approve the review as "bdd-user"
    And I run the export worker once
    Then the export image and sidecar should exist
    And the final job status should be "completed"

  Scenario: Validation failure blocks downstream stages
    Given a temporary Caipture test environment with CV min bytes 10000000
    And valid front and back PNG inputs with OCR sidecar text "Summer 1934 Enschede"
    When I create a new processing job
    And I run the CV worker once
    Then the job status should be "validation_failed"
    When I run the OCR and metadata workers once
    Then no OCR jobs should be processed
    And no metadata jobs should be processed

  Scenario: Web page upload flow with fixture files
    Given a temporary Caipture test environment
    And the web server is started for browser testing
    When I open the browser page "/"
    Then the page should contain "Caipture Control Center"
    When I upload fixture files through the web page form
    Then a job should be created from web upload
    And the central journal should contain web upload actions
