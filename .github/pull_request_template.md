# Summary

Briefly describe what this PR changes and why.

## Changes

*
*
*

## Related Issue / Task

Closes #

## CI / Automated Checks

CI runs automatically when this PR is opened or updated.

**Current CI status:** See the GitHub **Checks** section for the live pass/fail state.

Expected automated checks:

* Backend tests
* Frontend tests
* Build
* Lint / static analysis
* Other configured GitHub Actions checks

> Do not manually mark automated CI checks as passed. GitHub is the source of truth for CI status.

## How to Pull and Test This Branch

```powershell id="c2x0vm"
git fetch origin
git switch <branch-name>
git pull
```

If the branch does not exist locally:

```powershell id="z1ngw8"
git fetch origin
git switch --track origin/<branch-name>
```

## Setup / Migration Steps

List anything that must be done before testing.

Examples:

* Run database migrations
* Install/update dependencies
* Reset or seed the test database
* Update environment variables
* Restart the backend/frontend

Commands:

```powershell id="cfckm3"
# Add required setup commands here
```

## Manual Testing Plan

### Backend

* [ ] Backend starts successfully
* [ ] New/updated backend functionality works as expected
* [ ] No unexpected errors appear in backend logs

### Frontend

* [ ] Frontend starts successfully
* [ ] Page/component loads without errors
* [ ] New/updated functionality works as expected
* [ ] Existing related functionality still works
* [ ] No unexpected browser console errors

### Feature-Specific Testing

1.
2.
3.
4.

Expected result:

*

### Regression Testing

* [ ]
* [ ]
* [ ]

## Database / Test Data

* [ ] No database changes
* [ ] Database migration included
* [ ] Test data updated
* [ ] `seed_test_db.py --reset` tested successfully, if applicable

Describe any database or seed-data changes:

> None

## Screenshots / UI Changes

Before:

> N/A

After:

> N/A

## Known Issues / Limitations

> None

## Review Checklist

* [ ] Changes are limited to the intended scope
* [ ] Code follows existing project structure/style
* [ ] Version updated where required
* [ ] Tests added or updated where appropriate
* [ ] Documentation updated where appropriate
* [ ] README/changelog updated if required
* [ ] No debug code, temporary files, or credentials committed
* [ ] Manual testing completed
* [ ] User acceptance testing completed

## Ready to Merge When

* GitHub CI checks are passing
* Required review is complete
* Manual testing passes
* User acceptance testing passes
