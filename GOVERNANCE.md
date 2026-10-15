# Project governance

This document explains how people can propose, review, and maintain Dayglance. GitHub permissions and branch rules enforce some of these actions; the rest are project working practices.

## Roles

### Project owner

The repository is owned by the `mderdouri` personal GitHub account. The owner is responsible for project direction, repository settings, collaborator invitations and removals, releases, and the final decision to merge or decline changes. The owner is included in this process, not exempt from documenting it.

An owner can push and merge changes directly. For substantial changes, using a pull request gives the owner a visible discussion and review record. The owner cannot provide an independent approval of their own work; when no other reviewer is available, record that the change was owner-reviewed without independent review.

### Community member

Anyone can read and fork the public repository, open an issue, comment, or propose a change from a fork. A community member does not receive permission to push to the main repository just by opening an issue or pull request.

### Contributor

Contributors propose changes through a pull request, normally from a fork. No invitation or direct repository write permission is needed to do this. A pull request is a proposal; it does not grant merge rights or guarantee acceptance.

### Reviewer

Reviewers examine a pull request, ask questions, suggest changes, and submit a review. GitHub's default for public repositories allows any GitHub user to approve or request changes on a public pull request, unless the repository owner enables review limits. A review is feedback; it does not grant the reviewer permission to change the repository or merge the pull request.

### Collaborator

For a repository owned by a personal account, GitHub provides the owner and collaborator access levels. A collaborator can push changes and can create, review, and merge pull requests. The owner invites and removes collaborators. Invite only people who should have write and merge capability; the personal-repository model does not provide a read-only collaborator role.

### Maintainer

“Maintainer” describes project responsibilities, not a separate GitHub permission tier for this personal repository. A person acting as a maintainer must have collaborator write access. The owner remains responsible for repository administration and final project ownership.

## How changes are reviewed

1. Use the [bug report](.github/ISSUE_TEMPLATE/bug_report.yml) or [feature request](.github/ISSUE_TEMPLATE/feature_request.yml) form to describe the problem or idea. Avoid posting credentials or private location details.
2. For code changes, open a focused pull request from a branch or fork at a coherent, reviewable breakpoint. Keep unrelated work in separate PRs; for longer efforts, update the PR as validated increments are ready instead of waiting for a large batch. Explain the user-visible change and how it was checked.
3. Reviewers discuss the change in the pull request. The author responds to feedback and updates the proposal as needed.
4. The owner decides whether and when to merge. Do not merge solely because an approval icon is present; assess the change and its checks.

## Current GitHub enforcement

The public repository has Issues enabled and Discussions disabled. Its default branch is `main`. The GitHub Actions workflow (`CI / Verify`) is published. An active repository ruleset named **Protect main — PR and CI** targets the default branch. It requires changes to arrive through a pull request, requires `CI / Verify` to pass while the branch is up to date with `main`, requires review conversations to be resolved, blocks force pushes, and prevents deletion of the protected branch. Its standard required review count is zero; it also enables GitHub's extra-approval rule for unattributed changes. No bypass actors are configured.

The collaborator list and GitHub's separate review-limit setting remain unverified. Review limits are not recommended yet: on a personal public repository, limiting reviews to people with repository access means inviting those reviewers as collaborators with write access. Keep public reviews open while the project has no trusted second reviewer; the ordinary required-approval count is zero, with the extra-approval rule for unattributed changes described above. Revisit this if a trusted maintainer is added.

## Current safeguards and remaining recommendations

- The active ruleset applies pull requests, the up-to-date `CI / Verify` check, conversation resolution, branch deletion prevention, and force-push prevention to `main`.
- Keep required approvals at zero until a second independent reviewer is available. Then consider requiring one approval and dismissing stale approvals after new commits.
- Keep public issue and pull-request discussion open. Do not limit reviews to collaborators until trusted reviewers are invited with the write permissions that GitHub grants collaborators on personal repositories.
- Enable repository notifications (or a suitable email notification) and verify delivery, so issue and pull-request activity is not mistaken for a guaranteed direct message.

The `main` protections are configured through the active ruleset. Review limits are a separate control: GitHub's [review limits](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/managing-pull-request-reviews-in-your-repository) determine who may submit approvals; [branch protection](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches) and rulesets determine merge gates.
