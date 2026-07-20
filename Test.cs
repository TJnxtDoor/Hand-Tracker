using Xunit;
using CapstoneProject;

namespace CapstoneTests;

public class AppTests
{
    [Fact]
    public void TestLogItemPropertyAssignments()
    {
        // Arrange
        var item = new LogItem();

        // Act
        item.Letter = "V";
        item.Fingers = 2;

        // Assert
        Assert.Equal("V", item.Letter);
        Assert.Equal(2, item.Fingers);
    }

    [Fact]
    public void TestDataTimestampInitializes()
    {
        // Arrange & Act
        var item = new LogItem { Letter = "S" };

        // Assert
        Assert.True(item.CreatedAt <= DateTime.Now);
    }
}