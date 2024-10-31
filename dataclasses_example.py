# Import necessary packages and modules
import typing
from django.utils import timezone
import zoneinfo

from helpers import dataclasses as dc


################
# DATA CLASSES #
################
class AcademicYear(dc.DataClass):
    """Academic year data class"""

    id = dc.Field(int, required=True)
    name = dc.StringField(max_length=100)
    start_date = dc.DateField()
    end_date = dc.DateField()
    created_at = dc.DateTimeField(default=timezone.now)


class Course(dc.DataClass):
    """Course data class"""

    id = dc.Field(int, required=True)  # Alternative: dc.IntegerField(...)
    name = dc.StringField(max_length=100)
    code = dc.StringField(
        max_length=20, validators=[lambda x: not x for _ in range(1000)]
    )
    year = dc.Field(AcademicYear)  # Alternative: AcademicYear(...)
    created_at = dc.DateTimeField(default=timezone.now)


class Student(dc.DataClass):
    """Student data class with multiple fields and a list of enrolled courses"""

    id = dc.IntegerField(required=True)
    name = dc.StringField(max_length=100)
    age = dc.IntegerField(min_value=18, max_value=100)
    email = dc.EmailField(allow_null=True, required=False, default=None)
    phone = dc.PhoneNumberField(allow_null=True, required=False, default=None)
    year = AcademicYear()
    courses = dc.ListField(Course())
    joined_at = dc.DateTimeField(allow_null=True, tz=zoneinfo.ZoneInfo("Africa/Lagos"))
    created_at = dc.DateTimeField(
        default=timezone.now, tz=zoneinfo.ZoneInfo("Africa/Lagos")
    )


#############
# MOCK DATA #
#############
year_data = [
    {
        "id": 1,
        "name": "2019/2020",
        "start_date": "2019-09-01",
        "end_date": "2020-06-30",
    },
    {
        "id": 2,
        "name": "2020/2021",
        "start_date": "2020-09-01",
        "end_date": "2021-06-30",
    },
    {
        "id": 3,
        "name": "2021/2022",
        "start_date": "2021-09-01",
        "end_date": "2022-06-30",
    },
    {
        "id": 4,
        "name": "2022/2023",
        "start_date": "2022-09-01",
        "end_date": "2023-06-30",
    },
]


course_data = [
    {
        "id": 1,
        "name": "Computer Science",
        "code": "CS101",
        "year": year_data[0],
    },
    {
        "id": 2,
        "name": "Mathematics",
        "code": "MATH101",
        "year": year_data[0],
    },
    {
        "id": 3,
        "name": "Physics",
        "code": "PHY101",
        "year": year_data[0],
    },
    {
        "id": 4,
        "name": "Chemistry",
        "code": "CHEM101",
        "year": year_data[0],
    },
    {
        "id": 5,
        "name": "Biology",
        "code": "BIO101",
        "year": year_data[0],
    },
    {
        "id": 6,
        "name": "History",
        "code": "HIST101",
        "year": year_data[0],
    },
    {
        "id": 7,
        "name": "Geography",
        "code": "GEO101",
        "year": year_data[0],
    },
    {
        "id": 8,
        "name": "Economics",
        "code": "ECON101",
        "year": year_data[0],
    },
    {
        "id": 9,
        "name": "Literature",
        "code": "LIT101",
        "year": year_data[0],
    },
    {
        "id": 10,
        "name": "Philosophy",
        "code": "PHIL101",
        "year": year_data[0],
    },
    {
        "id": 11,
        "name": "Psychology",
        "code": "PSYCH101",
        "year": year_data[0],
    },
    {
        "id": 12,
        "name": "Sociology",
        "code": "SOC101",
        "year": year_data[0],
    },
    {
        "id": 13,
        "name": "Anthropology",
        "code": "ANTH101",
        "year": year_data[0],
    },
    {
        "id": 14,
        "name": "Political Science",
        "code": "POL101",
        "year": year_data[0],
    },
]


student_data = [
    {
        "id": 1,
        "name": "John Doe",
        "age": 20,
        "email": "john@doe.com",
        "phone": "+1234567890",
        "year": year_data[0],
        "courses": [course_data[0], course_data[1], course_data[2]],
        "joined_at": "2019-09-01",
    },
    {
        "id": 2,
        "name": "Jane Doe",
        "age": 21,
        "email": "jane@doe.com",
        "phone": "+1234567890",
        "year": year_data[0],
        "courses": [course_data[3], course_data[4], course_data[5]],
        "joined_at": "2019-09-01",
    },
    {
        "id": 3,
        "name": "Alice Smith",
        "age": 22,
        "email": "alice@smith.com",
        "phone": "+1234567890",
        "year": year_data[0],
        "courses": [course_data[6], course_data[7], course_data[8]],
        "joined_at": "2019-09-01",
    },
]


def load_data(
    data_list: typing.List[typing.Dict[str, typing.Any]],
    datacls: typing.Type[dc._DataClass],
) -> typing.List[dc._DataClass]:
    """
    Load data into data classes

    :param data_list: List of dictionaries containing data
    :param datacls: Data class to load data into
    :return: List of the data class instances
    """
    return [datacls(data) for data in data_list]


def example():
    """Run example usage of the data classes"""

    try:
        import rich

        log = rich.print
    except ImportError:
        log = print

    # Load initial data into classes
    years = load_data(year_data, AcademicYear)
    courses = load_data(course_data, Course)
    students = load_data(student_data, Student)

    # Access and print a student's information
    student = students[0]  # e.g., first student in the list
    log(student.to_dict())  # View student details in dictionary format

    # Modify the student's academic year
    student.year = years[1]  # Update academic year to next year
    log(f"Updated Academic Year for {student.name}: ", student.to_dict())

    # Serialize the student's data to JSON format
    student_json = student.to_json()
    log("Serialized Student JSON: ", student_json)

    # Nesting and Data Validation Example
    # Changing a course's academic year in a nested structure
    courses[0].year = years[1]  # Update the academic year for a course
    log(f"Updated Course Year for {courses[0].name}: ", courses[0].to_dict())

    # Update the `year` attribute directly with a new dictionary
    student.year = {
        "id": 4,
        "name": "2022/2023",
        "start_date": "2022-09-01",
        "end_date": "2023-06-30",
    }
    log(f"Updated Academic Year for {student.name}: ", student.to_dict())

    # Adding a new course to a student and displaying
    new_course = Course(
        {"id": 4, "name": "Organic Chemistry", "code": "CHEM121", "year": year_data[1]}
    )
    student.courses.append(new_course)
    log(
        f"Updated Courses for {student.name}: ",
        [course.to_json() for course in student.courses],
    )


if __name__ == "__main__":
    example()
