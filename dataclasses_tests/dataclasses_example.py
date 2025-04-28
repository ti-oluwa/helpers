# Import necessary packages and modules
import typing
from datetime import datetime

from ..generics.data_utils import dataclasses as dc
from ..generics.utils.profiling import timeit
from .mock_data import course_data, student_data, year_data


_DataClass_co = typing.TypeVar("_DataClass_co", bound=dc.DataClass, covariant=True)


################
# DATA CLASSES #
################
class AcademicYear(dc.DataClass, slots=True):
    """Academic year data class"""

    id = dc.Field(int, required=True)
    name = dc.StringField(max_length=100)
    start_date = dc.DateField(input_formats=["%d-%m-%Y", "%d/%m/%Y"])
    end_date = dc.DateField(input_formats=["%d-%m-%Y", "%d/%m/%Y"])
    created_at = dc.DateTimeField(default=datetime.now, tz="Africa/Lagos")


class Course(dc.DataClass, slots=True):
    """Course data class"""

    id = dc.Field(
        int, required=True, allow_null=True
    )  # Alternative: dc.IntegerField(...)
    name = dc.StringField(max_length=100)
    code = dc.StringField(max_length=20)
    year = dc.NestedField(AcademicYear, lazy=False)
    created_at = dc.DateTimeField(default=datetime.now)


class Student(dc.DataClass, slots=True):
    """Student data class with multiple fields and a list of enrolled courses"""

    id = dc.IntegerField(required=True)
    name = dc.StringField(max_length=100)
    age = dc.IntegerField(min_value=30, max_value=100)
    email = dc.EmailField(allow_null=True, default=None)
    phone = dc.StringField(allow_null=True, default=None)
    year = dc.NestedField(AcademicYear, lazy=False)
    courses = dc.ListField(
        child=dc.NestedField(Course, lazy=False),
    )
    joined_at = dc.DateTimeField(allow_null=True, tz="Africa/Lagos")
    created_at = dc.DateTimeField(default=datetime.now, tz="Africa/Lagos")


def load_data(
    data_list: typing.List[typing.Dict[str, typing.Any]],
    datacls: typing.Type[_DataClass_co],
) -> typing.List[_DataClass_co]:
    """
    Load data into data classes

    :param data_list: List of dictionaries containing data
    :param datacls: Data class to load data into
    :return: List of the data class instances
    """
    # raise
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

    for student in students:
        student.serialize(fmt="python", depth=1)

    for course in courses:
        course.serialize(fmt="python", depth=1)

    for year in years:
        year.serialize(fmt="python", depth=1)

    # # Access and print a student's information
    # student = students[0]  # e.g., first student in the list
    # log(student.serialize())  # View student details in dictionary format
    # # Modify the student's academic year
    # student.year = years[1]  # Update academic year to next year
    # log(f"Updated Academic Year for {student.name}: ", student.serialize())

    # # Serialize the student's data to JSON format
    # student_json = student.serialize(fmt="json")
    # log("Serialized Student JSON: ", student_json)

    # # Nesting and Data Validation Example
    # # Changing a course's academic year in a nested structure
    # courses[0].year = years[1]  # Update the academic year for a course
    # log(f"Updated Course Year for {courses[0].name}: ", courses[0].serialize())

    # # Update the `year` attribute directly with a new dictionary
    # student.year = {
    #     "id": 4,
    #     "name": "2022/2023",
    #     "start_date": "2022-09-01",
    #     "end_date": "2023-06-30",
    # }
    # log(f"Updated Academic Year for {student.name}: ", student.serialize())

    # # Adding a new course to a student and displaying
    # new_course = Course(
    #     {"id": 4, "name": "Organic Chemistry", "code": "CHEM121", "year": year_data[1]}
    # )
    # student.courses.append(new_course)
    # log(
    #     f"Updated Courses for {student.name}: ",
    #     [course.serialize(fmt="json") for course in student.courses],
    # )

    # # Update student age
    # log(student.name, "is", student.age, "years old")
    # student.age += 3
    # log(student.name, "is now", student.age, "years old")


@timeit("dataclasses_test")
def test(n: int = 1):
    """Run the dataclasses example multiple times"""
    for _ in range(n):
        example()
