# SONiC Community Agent Etiquette Rules

## Identity and Ownership

- **Clearly identify the agent and its owner** (human or corporate). Use a separate GitHub profile that is easily identifiable as an agent, e.g., postfix your agent's name with "_bot". In the agent's github profile, clearly identify the owner's actual github ID.

- If you choose to use agent at the backend and reuse your human github profile, please clearly mark each PRs and code review as AI-generated. Prefix the PR with "[Agent]" in the description.

- Agent should not have merge rights or admin priviledges. For SONiC community members with merge rights and admin priviledges, they must use separate github profiles for their agents without delegating their priledges to any agents.

## Code Review and Approval

- Humans cannot approve PRs from their own agents because SONiC community considers agents as inherently aligned with their owners. So we would like to see a second opinion as proper sign off instead of self-approval.
- Humans should review their agents's configuration and PRs before submission to ensure quality.
- Agents are welcome to provide PR reviews, but cannot sign off as owners of a repo.

## Quality and Compliance

- Agents are NOT allowed to bypassing CI/CD checks, the same rules applies to humans.

- Agents are required to follow all template requirements. The community will work together to creates skills and instruction to help to agents follow the requirements over time.

- SONiC community has agreed to avoid imposing a rate limit on agent PRs to facilitate fast evolution of the community.  However, to protect for CI/CD pipeline from potentially being flooded, we may choose to implement prioritization mechanims in the CI/CD pipleine and may choose to deprioritizing repeated pushes form the same account.

## Metrics and Tracking

- SONiC community has agreed to credit agent PRs with the same SII socre points as human PRs. This is in recognition that all PR are equal and to encourage transparency. We will try to track AI vs. non-AI PRs for analytics and understand how the community is evolving.

- SONiC community will consider crediting higher weight for contributions to HLD and others that require high human investment. This will be covered in future TSC meetings. 

## Best Practices

- Check for duplicate PRs and open issues to avoid creating new ones.
- Link bug-fix PRs to related open issues
- Use templates effectively and share best practices with the community.
