# Import necessary packages and modules
import pickle
import typing
from datetime import datetime

from ..generics.data_utils import dataclasses as dc
from ..generics.utils.profiling import timeit, profileit
from .mock_data import course_data, student_data, year_data


_DataClass_co = typing.TypeVar("_DataClass_co", bound=dc.DataClass, covariant=True)


################
# DATA CLASSES #
################
class AcademicYear(
    dc.DataClass,
    eq=True,
    hash=True,
    slots=True,
):
    """Academic year data class"""

    id = dc.Field(int, required=True)
    name = dc.StringField(max_length=100)
    start_date = dc.DateField(input_formats=["%d-%m-%Y", "%d/%m/%Y"])
    end_date = dc.DateField(input_formats=["%d-%m-%Y", "%d/%m/%Y"])
    created_at = dc.DateTimeField(default=dc.Factory(datetime.now), tz="Africa/Lagos")


class Course(
    dc.DataClass,
    eq=True,
    hash=True,
    slots=True,
):
    """Course data class"""

    id = dc.Field(int, required=True, allow_null=True)
    name = dc.StringField(max_length=100)
    code = dc.StringField(max_length=20)
    year = dc.NestedField(AcademicYear, lazy=False)
    created_at = dc.DateTimeField(default=dc.Factory(datetime.now))


class PersonalInfo(
    dc.DataClass,
    eq=True,
    hash=True,
    slots=True,
):
    """Personal information data class"""

    name = dc.StringField(max_length=100)
    age = dc.IntegerField(min_value=0, max_value=100)
    email = dc.EmailField(allow_null=True, default=None)
    phone = dc.PhoneNumberField(allow_null=True, default=None)


class Student(
    PersonalInfo,
    eq=True,
    hash=True,
    slots=True,
):
    """Student data class with multiple fields and a list of enrolled courses"""

    id = dc.IntegerField(required=True)
    year = dc.NestedField(AcademicYear, lazy=False)
    courses = dc.ListField(
        child=dc.NestedField(Course, lazy=False),
    )
    joined_at = dc.DateTimeField(allow_null=True, tz="Africa/Lagos")
    created_at = dc.DateTimeField(default=dc.Factory(datetime.now), tz="Africa/Lagos")


def load_data(
    data_list: typing.List[typing.Dict[str, typing.Any]],
    cls: typing.Type[_DataClass_co],
) -> typing.List[_DataClass_co]:
    """
    Load data into data classes

    :param data_list: List of dictionaries containing data
    :param cls: Data class to load data into
    :return: List of the data class instances
    """
    # raise
    return [dc.deserialize(cls, data) for data in data_list]


def example():
    """Run example usage of the data classes"""

    # try:
    #     import rich

    #     log = rich.print
    # except ImportError:
    #     log = print

    # Load initial data into classes
    years = load_data(year_data, AcademicYear)
    courses = load_data(course_data, Course)
    students = load_data(student_data, Student)

    for student in students:
        dc.serialize(student, fmt="json", depth=2)

    for course in courses:
        dc.serialize(course, fmt="json", depth=2)

    for year in years:
        dc.serialize(year, fmt="json", depth=2)

    # dump = pickle.dumps(students)
    # loaded_students = pickle.loads(dump)
    # log(
    #     "Loaded Students: ",
    #     [dc.serialize(student, fmt="python") for student in loaded_students],
    # )

    # # Access and print a student's information
    # student = students[0]  # e.g., first student in the list
    # log(dc.serialize(student, depth=2))  # View student details in dictionary format
    # Modify the student's academic year
    # student.year = years[1]  # Update academic year to next year
    # log(f"Updated Academic Year for {student.name}: ", dc.serialize(student))

    # # Serialize the student's data to JSON format
    # student_json = dc.serialize(student, fmt="json", depth=2)
    # log("Serialized Student JSON: ", student_json)

    # # Nesting and Data Validation Example
    # # Changing a course's academic year in a nested structure
    # courses[0].year = years[1]  # Update the academic year for a course
    # log(f"Updated Course Year for {courses[0].name}: ", dc.serialize(courses[0]))

    # # Update the `year` attribute directly with a new dictionary
    # student.year = {
    #     "id": 4,
    #     "name": "2022/2023",
    #     "start_date": "2022-09-01",
    #     "end_date": "2023-06-30",
    # }
    # log(f"Updated Academic Year for {student.name}: ", dc.serialize(student, depth=2))

    # # Adding a new course to a student and displaying
    # new_course = Course(
    #     {"id": 4, "name": "Organic Chemistry", "code": "CHEM121", "year": year_data[1]}
    # )
    # student.courses.append(new_course)
    # log(
    #     f"Updated Courses for {student.name}: ",
    #     [dc.serialize(course, fmt="json", depth=2) for course in student.courses],
    # )

    # # Update student age
    # log(student.name, "is", student.age, "years old")
    # student.age += 3
    # log(student.name, "is now", student.age, "years old")


@profileit("dataclasses_test", max_rows=30, output="rich")
def test(n: int = 1):
    """Run the dataclasses example multiple times"""
    for _ in range(n):
        example()
